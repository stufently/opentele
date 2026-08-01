"""Pyrogram bridge — convert between `tdata` and Pyrogram sessions.

Upstream `thedemons/opentele` listed Pyrogram support as an "incoming feature"
and never shipped it. `timka-123/opentele` attempted it; that implementation
does not run (it calls `account.isLoaded()` before `account` is bound, and its
`writeKeys` change stamps `MainDcId` onto every key, corrupting multi-DC
`serializeMtpAuthorization()` output). This is a clean reimplementation that
reuses the same code path as the Telethon bridge.

Pyrogram is an **optional** dependency: nothing here is imported at package
import time. Install one of the distributions that provide the `pyrogram`
package — `pyrofork` (what `opentele-ng[pyrogram]` pulls in), vanilla
`pyrogram`, or `kurigram`.

Session data is written through Pyrogram's own `Storage` API rather than by
packing `SESSION_STRING_FORMAT` here, so a change to that format in any of
those distributions cannot silently produce a corrupt session.
"""
from __future__ import annotations

import typing
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional

from ..exception import (
    Expects,
    PyrogramNotInstalled,
    PyrogramSessionUnsupported,
    PyrogramUnauthorized,
)

if typing.TYPE_CHECKING:  # nocov - typing only, never imported at runtime
    from pyrogram import Client


class PyrogramCredentials(NamedTuple):
    """What a Pyrogram session carries that `tdata` needs."""

    dc_id: int
    auth_key: bytes
    user_id: Optional[int]
    test_mode: bool
    is_bot: bool


def _import_pyrogram() -> Any:
    """Import `pyrogram`, or raise a `PyrogramNotInstalled` that says how to fix it."""
    try:
        import pyrogram  # type: ignore
    except ImportError as exc:  # nocov - depends on the environment
        raise PyrogramNotInstalled(
            "Pyrogram is not installed. Install it with "
            "`pip install opentele-ng[pyrogram]`, or any distribution providing "
            "the `pyrogram` package (pyrofork, pyrogram, kurigram)."
        ) from exc
    return pyrogram


def pyrogram_layer() -> Optional[int]:
    """MTProto layer the installed Pyrogram speaks, or `None` if unreadable.

    Pyrogram ships its own generated schema, so it is generally **not** on the
    same layer as Telethon — pyrofork 2.3.69 announces 220 where Telethon 1.44
    announces 227. Anything that advertises a Telegram Desktop version on a
    Pyrogram client has to align with *this* number, not Telethon's.
    """
    try:
        from pyrogram.raw.all import layer  # type: ignore

        return int(layer)
    except Exception:  # nocov - depends on the installed distribution
        return None


def desktop_version_for_pyrogram(app_version: str) -> str:
    """Re-point a Telegram Desktop `app_version` at Pyrogram's MTProto layer.

    Returns `app_version` untouched when it is not a Telegram Desktop version
    string we have layer data for (an Android/iOS/web fingerprint, or a custom
    one), or when the layer cannot be read.
    """
    from ..api import API, _pick_versions_for_layer

    desktop = API.TelegramDesktop
    bare = app_version.removesuffix(" x64") if app_version else ""
    if bare not in desktop.TELEGRAM_DESKTOP_LAYERS:
        return app_version

    layer = pyrogram_layer()
    if layer is None:  # nocov - depends on the installed distribution
        return app_version

    candidates = _pick_versions_for_layer(
        desktop.TELEGRAM_DESKTOP_VERSIONS, desktop.TELEGRAM_DESKTOP_LAYERS, layer
    )
    return f"{candidates[0]} x64" if candidates else app_version


async def _populate(
    storage: Any,
    api_id: int,
    dc_id: int,
    auth_key: bytes,
    user_id: int,
    test_mode: bool = False,
    is_bot: bool = False,
) -> None:
    """Write MTProto credentials into an already-open Pyrogram storage."""
    await storage.dc_id(dc_id)
    await storage.api_id(api_id)
    await storage.test_mode(test_mode)
    await storage.auth_key(auth_key)
    await storage.user_id(user_id)
    await storage.is_bot(is_bot)


async def export_session_string(
    api_id: int,
    dc_id: int,
    auth_key: bytes,
    user_id: int,
    name: str = "opentele",
    test_mode: bool = False,
    is_bot: bool = False,
) -> str:
    """Build a Pyrogram session string from raw MTProto credentials."""
    pyrogram = _import_pyrogram()
    storage = pyrogram.storage.MemoryStorage(name)
    await storage.open()
    try:
        await _populate(storage, api_id, dc_id, auth_key, user_id, test_mode, is_bot)
        return await storage.export_session_string()
    finally:
        await storage.close()


def _client_params(api: Any, align_layer: bool, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    app_version = api.app_version
    if align_layer:
        app_version = desktop_version_for_pyrogram(app_version)

    params: Dict[str, Any] = {
        "api_id": api.api_id,
        "api_hash": api.api_hash,
        "app_version": app_version,
        "device_model": api.device_model,
        "system_version": api.system_version,
        "lang_code": api.lang_code,
        "system_lang_code": api.system_lang_code,
        "lang_pack": api.lang_pack,
    }
    params.update(kwargs)
    return params


def _session_path(pyrogram: Any, client: Any, name: str) -> Optional[Path]:
    """Where this client's `.session` file will actually land, or `None` when
    the session is not file-backed and there is nothing on disk to guard —
    a caller-supplied `storage=`, or the Mongo backend some distributions ship
    (whose `database` is a live handle, not a path).

    Not the process CWD: an omitted `workdir` resolves to the *entry script's*
    directory (`Path(sys.argv[0]).parent`), so probing `os.getcwd()` would
    guard a path Pyrogram never writes. `client.storage.database` is the file
    Pyrogram itself opens; the `workdir` join is a fallback for distributions
    that name the attribute differently.
    """
    file_storage = getattr(pyrogram.storage, "FileStorage", None)
    if file_storage is not None and not isinstance(client.storage, file_storage):
        return None
    database = getattr(client.storage, "database", None)
    if database is not None:
        return Path(database)
    # nocov - only reached by a distribution that renamed `database`
    extension = getattr(client.storage, "FILE_EXTENSION", ".session")
    return Path(client.workdir) / f"{name}{extension}"


async def make_client(
    api: Any,
    dc_id: int,
    auth_key: bytes,
    user_id: int,
    name: str = "opentele",
    in_memory: bool = True,
    align_layer: bool = True,
    overwrite: bool = False,
    **kwargs: Any,
) -> Client:
    """Build a `pyrogram.Client` for these credentials, carrying `api`'s fingerprint.

    Unlike Telethon, Pyrogram accepts `lang_pack` directly, so the whole
    `APIData` fingerprint — including the official-app-only `lang_pack` — goes
    on the wire as-is.

    `app_version` is re-pointed at Pyrogram's MTProto layer when it is a
    Telegram Desktop version (see `desktop_version_for_pyrogram()`); the value
    aligned at import time in `opentele.api` follows *Telethon's* layer, which
    is a different number. Pass `align_layer=False` to keep `api.app_version`
    verbatim.

    `in_memory=True` (default) keeps the session in memory — converting a
    session should not write a `.session` file into the caller's working
    directory as a side effect. `in_memory=False` writes `<name>.session` in
    `workdir`; omit it and Pyrogram puts the file next to the entry script
    (`sys.argv[0]`'s directory), which is *not* the process CWD.

    An existing file of that name raises `FileExistsError` unless
    `overwrite=True`, which **deletes** it first. Writing into it would only
    replace the credentials row: Pyrogram's `peers`, `usernames` and
    `update_state` tables would survive and the new session would inherit the
    previous account's cached contacts.
    """
    pyrogram = _import_pyrogram()
    params = _client_params(api, align_layer, kwargs)

    if in_memory:
        # A session string always selects MemoryStorage, whatever `in_memory`
        # says — so the file case must not pass one.
        session_string = await export_session_string(
            api_id=api.api_id,
            dc_id=dc_id,
            auth_key=auth_key,
            user_id=user_id,
            name=name,
        )
        return pyrogram.Client(
            name, session_string=session_string, in_memory=True, **params
        )

    # Build the client first: only it knows where the session lands. Pyrogram
    # resolves `workdir` itself, and constructing a `FileStorage` does not
    # touch the file — that happens in `open()` below.
    client = pyrogram.Client(name, in_memory=False, **params)
    session_file = _session_path(pyrogram, client, name)
    if session_file is not None and session_file.exists():
        if not overwrite:
            raise FileExistsError(
                f"{session_file} already exists. Pyrogram would keep its peers/"
                "usernames/update_state tables, mixing the previous account's "
                "cached data into this session. Pass a different `name`, or "
                "`overwrite=True` to replace the file."
            )
        session_file.unlink()

    await client.storage.open()
    try:
        await _populate(client.storage, api.api_id, dc_id, auth_key, user_id)
        await client.storage.save()
    finally:
        await client.storage.close()
    return client


async def read_credentials(client: Client) -> PyrogramCredentials:
    """Read MTProto credentials out of a Pyrogram client's storage.

    Opens the storage if the client has not done so yet, and closes it again in
    that case — leaving a SQLite connection open behind the caller's back would
    leak it, and Pyrogram's own `connect()` reopens the storage anyway, dropping
    the reference to ours.

    A client built from a session string parses it in `storage.open()`, which
    normally happens inside `connect()`. Re-opening an already-open storage
    would rebuild it from scratch — for a live, connected client that discards
    the in-memory auth state — so probe first. A falsy `dc_id` counts as "not
    open" as well as an exception: distributions differ on whether reading an
    unopened storage raises or quietly returns `None`, and an authorized
    session always has a `dc_id`.
    """
    opened_here = False
    try:
        dc_id = await client.storage.dc_id()
    except Exception:  # nocov - narrow failure differs per distribution
        dc_id = None

    if not dc_id:
        await client.storage.open()
        opened_here = True
        dc_id = await client.storage.dc_id()

    try:
        auth_key = await client.storage.auth_key()
        Expects(
            bool(auth_key),
            PyrogramUnauthorized(
                "Pyrogram client has no auth_key — it is unauthorized, "
                "there is no session to convert"
            ),
        )

        user_id = await client.storage.user_id()
        test_mode = bool(await client.storage.test_mode())
        is_bot = bool(await client.storage.is_bot())
    finally:
        if opened_here:
            await client.storage.close()

    Expects(
        not test_mode,
        PyrogramSessionUnsupported(
            "This is a test-DC session. tdata written here always carries the "
            "production MTP config, so the auth key would be useless — convert "
            "a production session instead."
        ),
    )
    Expects(
        not is_bot,
        PyrogramSessionUnsupported(
            "This is a bot session. Telegram Desktop cannot sign in as a bot, "
            "so there is no meaningful tdata to write."
        ),
    )

    return PyrogramCredentials(
        dc_id=int(dc_id),
        auth_key=auth_key,
        user_id=(int(user_id) if user_id else None),
        test_mode=test_mode,
        is_bot=is_bot,
    )
