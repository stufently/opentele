"""Phase 6 — Pyrogram bridge (`opentele.tl.pyrogram_bridge`).

Everything here is offline: sessions are built from a dummy AuthKey with the
same helper the tdata round-trip tests use, so nothing touches Telegram.

The invariant under test is that credentials survive the round trip
tdata → Pyrogram session string → tdata unchanged, and that the device
fingerprint of the chosen `APIData` reaches the client — including
`lang_pack`, which Telethon cannot send at all.
"""
from __future__ import annotations

import sqlite3

import pytest
from opentele.api import API, APIData, CreateNewSession, UseCurrentSession
from opentele.exception import (
    LoginFlagInvalid,
    PyrogramSessionUnsupported,
    PyrogramUnauthorized,
)
from opentele.td import TDesktop
from opentele.td import shared as td
from opentele.td.account import Account
from opentele.td.auth import AuthKeyType
from opentele.td.configs import DcId
from opentele.tl import pyrogram_bridge as pyro

pyrogram = pytest.importorskip("pyrogram", reason="optional extra: opentele-ng[pyrogram]")

DUMMY_KEY = bytes(range(256))
USER_ID = 88884444
DC_ID = 2


def _build_tdesktop() -> TDesktop:
    tdesk = TDesktop()
    tdesk._TDesktop__generateLocalKey()
    account = Account(owner=tdesk, api=API.TelegramDesktop, index=0)
    authkey = td.AuthKey(DUMMY_KEY, AuthKeyType.ReadFromFile, DcId(DC_ID))
    account._setMtpAuthorizationCustom(DcId(DC_ID), USER_ID, [authkey])
    tdesk._addSingleAccount(account)
    return tdesk


# === session string ===


async def test_export_session_string_roundtrips_credentials() -> None:
    """The string we hand to Pyrogram decodes back to the same credentials."""
    session_string = await pyro.export_session_string(
        api_id=API.TelegramDesktop.api_id,
        dc_id=DC_ID,
        auth_key=DUMMY_KEY,
        user_id=USER_ID,
    )

    storage = pyrogram.storage.MemoryStorage("probe", session_string)
    await storage.open()
    try:
        assert await storage.dc_id() == DC_ID
        assert await storage.user_id() == USER_ID
        assert await storage.auth_key() == DUMMY_KEY
    finally:
        await storage.close()


async def test_make_client_carries_api_fingerprint() -> None:
    api = API.TelegramAndroid  # not a desktop fingerprint → app_version verbatim
    client = await pyro.make_client(
        api, dc_id=DC_ID, auth_key=DUMMY_KEY, user_id=USER_ID
    )

    assert client.api_id == api.api_id
    assert client.api_hash == api.api_hash
    assert client.app_version == api.app_version
    assert client.device_model == api.device_model
    assert client.system_version == api.system_version
    # Telethon cannot set lang_pack — Pyrogram can, and an official app always
    # sends one. Losing it here would undo the point of using official APIs.
    assert client.lang_pack == api.lang_pack


async def test_make_client_defaults_to_in_memory() -> None:
    """Converting a session must not drop a .session file in the cwd."""
    client = await pyro.make_client(
        API.TelegramDesktop, dc_id=DC_ID, auth_key=DUMMY_KEY, user_id=USER_ID
    )
    assert isinstance(client.storage, pyrogram.storage.MemoryStorage)


# === MTProto layer alignment ===


async def test_desktop_app_version_follows_pyrogram_layer() -> None:
    """Pyrogram ships its own schema, so it is on a different layer than
    Telethon — advertising Telethon's matching build over a Pyrogram
    connection would be the exact mismatch the layer table exists to stop."""
    layer = pyro.pyrogram_layer()
    assert isinstance(layer, int)

    client = await pyro.make_client(
        API.TelegramDesktop, dc_id=DC_ID, auth_key=DUMMY_KEY, user_id=USER_ID
    )
    bare = client.app_version.removesuffix(" x64")
    assert API.TelegramDesktop.TELEGRAM_DESKTOP_LAYERS[bare] == layer


async def test_align_layer_false_keeps_api_version() -> None:
    client = await pyro.make_client(
        API.TelegramDesktop,
        dc_id=DC_ID,
        auth_key=DUMMY_KEY,
        user_id=USER_ID,
        align_layer=False,
    )
    assert client.app_version == API.TelegramDesktop.app_version


def test_non_desktop_versions_are_left_alone() -> None:
    """Only Telegram Desktop version strings are re-pointed; Android/iOS/web
    fingerprints have no layer table and must pass through untouched."""
    for value in ["12.9.0 (6966)", "12.9.2", "2.2", "", "totally custom"]:
        assert pyro.desktop_version_for_pyrogram(value) == value


# === file-backed sessions ===


async def test_in_memory_false_writes_a_session_file(tmp_path) -> None:
    """A session string always selects MemoryStorage regardless of `in_memory`,
    so the file path must not pass one — otherwise `in_memory=False` silently
    produces no file at all."""
    client = await pyro.make_client(
        API.TelegramDesktop,
        dc_id=DC_ID,
        auth_key=DUMMY_KEY,
        user_id=USER_ID,
        name="filemode",
        in_memory=False,
        workdir=str(tmp_path),
    )
    assert not isinstance(client.storage, pyrogram.storage.MemoryStorage)

    session_file = tmp_path / "filemode.session"
    assert session_file.exists(), f"no session file in {list(tmp_path.iterdir())}"

    # And it must be loadable again — a file that exists but holds nothing is
    # no better than no file.
    reopened = pyrogram.Client(
        "filemode",
        api_id=API.TelegramDesktop.api_id,
        api_hash=API.TelegramDesktop.api_hash,
        workdir=str(tmp_path),
    )
    await reopened.storage.open()
    try:
        assert await reopened.storage.auth_key() == DUMMY_KEY
        assert await reopened.storage.user_id() == USER_ID
        assert await reopened.storage.dc_id() == DC_ID
    finally:
        await reopened.storage.close()


async def test_in_memory_false_refuses_to_reuse_an_existing_file(tmp_path) -> None:
    """Writing into an existing session file would only replace the credentials
    row — Pyrogram's peers/usernames/update_state tables would survive and the
    new session would inherit the previous account's cached contacts."""
    kwargs = dict(
        dc_id=DC_ID, auth_key=DUMMY_KEY, user_id=USER_ID,
        name="reused", in_memory=False, workdir=str(tmp_path),
    )
    await pyro.make_client(API.TelegramDesktop, **kwargs)

    with pytest.raises(FileExistsError):
        await pyro.make_client(API.TelegramDesktop, **kwargs)


async def test_overwrite_replaces_the_file_wholesale(tmp_path) -> None:
    """`overwrite=True` starts from a fresh file, so nothing of the previous
    account survives — not even rows we never touch ourselves."""
    client = await pyro.make_client(
        API.TelegramDesktop, dc_id=DC_ID, auth_key=DUMMY_KEY, user_id=USER_ID,
        name="replaced", in_memory=False, workdir=str(tmp_path),
    )
    # Leave a trace of the "previous account" in a table make_client never writes.
    await client.storage.open()
    try:
        await client.storage.update_peers([(4242, 4242, "user", "olduser", None)])
        await client.storage.save()
    finally:
        await client.storage.close()

    other_key = bytes(range(255, -1, -1))
    await pyro.make_client(
        API.TelegramDesktop, dc_id=DC_ID, auth_key=other_key, user_id=99999,
        name="replaced", in_memory=False, workdir=str(tmp_path), overwrite=True,
    )

    reopened = pyrogram.Client(
        "replaced",
        api_id=API.TelegramDesktop.api_id,
        api_hash=API.TelegramDesktop.api_hash,
        workdir=str(tmp_path),
    )
    await reopened.storage.open()
    try:
        assert await reopened.storage.auth_key() == other_key
        assert await reopened.storage.user_id() == 99999
        with pytest.raises(KeyError):
            await reopened.storage.get_peer_by_username("olduser")
    finally:
        await reopened.storage.close()


async def test_existing_file_guard_follows_pyrogram_not_the_cwd(
    tmp_path, monkeypatch
) -> None:
    """Pyrogram's default `workdir` is the entry script's directory, never the
    process CWD, so a CWD-based guard would stat a path that is never written:
    the second conversion would silently inherit the first account's
    peers/usernames/update_state rows. Emulated with a Client whose default
    workdir is somewhere other than the CWD."""
    script_dir = tmp_path / "scriptdir"
    script_dir.mkdir()
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)

    class DefaultWorkdirClient(pyrogram.Client):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("workdir", str(script_dir))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(pyrogram, "Client", DefaultWorkdirClient)

    kwargs = dict(
        dc_id=DC_ID, auth_key=DUMMY_KEY, user_id=USER_ID,
        name="defaults", in_memory=False,
    )
    await pyro.make_client(API.TelegramDesktop, **kwargs)

    assert (script_dir / "defaults.session").exists()
    assert not (cwd / "defaults.session").exists()

    with pytest.raises(FileExistsError):
        await pyro.make_client(API.TelegramDesktop, **kwargs)

    # And `overwrite` must reach the same file — otherwise the "wholesale
    # replace" quietly degrades into an in-place credential swap.
    other_key = bytes(range(255, -1, -1))
    await pyro.make_client(
        API.TelegramDesktop, **{**kwargs, "auth_key": other_key}, overwrite=True
    )
    reopened = pyrogram.Client(
        "defaults",
        api_id=API.TelegramDesktop.api_id,
        api_hash=API.TelegramDesktop.api_hash,
        workdir=str(script_dir),
    )
    await reopened.storage.open()
    try:
        assert await reopened.storage.auth_key() == other_key
    finally:
        await reopened.storage.close()


async def test_non_file_storage_skips_the_file_guard(tmp_path, monkeypatch) -> None:
    """`in_memory=False` does not always mean "a file": a caller-supplied
    `storage=` (or a Mongo backend) has no path to check, and its `database`
    attribute is a live handle rather than one — treating it as a path would
    turn a supported setup into a TypeError."""
    monkeypatch.chdir(tmp_path)
    storage = pyrogram.storage.MemoryStorage("custom")

    client = await pyro.make_client(
        API.TelegramDesktop,
        dc_id=DC_ID,
        auth_key=DUMMY_KEY,
        user_id=USER_ID,
        name="custom",
        in_memory=False,
        storage=storage,
        workdir=str(tmp_path),
    )

    assert client.storage is storage
    assert not list(tmp_path.glob("*.session"))


# === Account / TDesktop bridges ===


async def test_account_to_pyrogram_uses_current_session() -> None:
    tdesk = _build_tdesktop()
    client = await tdesk.mainAccount.ToPyrogram()

    await client.storage.open()
    try:
        assert await client.storage.dc_id() == DC_ID
        assert await client.storage.user_id() == USER_ID
        assert await client.storage.auth_key() == DUMMY_KEY
    finally:
        await client.storage.close()


async def test_tdesktop_to_pyrogram_delegates_to_main_account() -> None:
    tdesk = _build_tdesktop()
    client = await tdesk.ToPyrogram()

    await client.storage.open()
    try:
        assert await client.storage.auth_key() == DUMMY_KEY
    finally:
        await client.storage.close()


async def test_from_pyrogram_rebuilds_the_account() -> None:
    """tdata → pyrogram → tdata keeps authKey, DC and user id identical."""
    source = _build_tdesktop()
    client = await source.ToPyrogram()

    restored = await TDesktop.FromPyrogram(client)

    assert restored.accountsCount == 1
    account = restored.mainAccount
    assert int(account.MainDcId) == DC_ID
    assert account.UserId == USER_ID
    assert account.authKey.key == DUMMY_KEY


async def test_from_pyrogram_produces_loadable_tdata(tmp_path) -> None:
    """The rebuilt client survives SaveTData/LoadTData — i.e. the account we
    construct from Pyrogram credentials is a real, serializable account, not
    just an in-memory object that looks right."""
    source = _build_tdesktop()
    client = await source.ToPyrogram()
    restored = await TDesktop.FromPyrogram(client)

    out = str(tmp_path / "tdata")
    restored.SaveTData(out)

    reloaded = TDesktop(out)
    assert reloaded.isLoaded()
    assert reloaded.mainAccount.authKey.key == DUMMY_KEY
    assert reloaded.mainAccount.UserId == USER_ID


async def test_from_pyrogram_rejects_create_new_session() -> None:
    tdesk = _build_tdesktop()
    client = await tdesk.ToPyrogram()

    with pytest.raises(LoginFlagInvalid):
        await TDesktop.FromPyrogram(client, flag=CreateNewSession)


async def test_from_pyrogram_rejects_unauthorized_client() -> None:
    """A client with no auth_key has no session to convert."""
    client = pyrogram.Client(
        "unauthorized",
        api_id=API.TelegramDesktop.api_id,
        api_hash=API.TelegramDesktop.api_hash,
        in_memory=True,
    )
    with pytest.raises(PyrogramUnauthorized):
        await TDesktop.FromPyrogram(client)


async def test_create_new_session_routes_kwargs_to_the_right_client(monkeypatch) -> None:
    """`**kwargs` configure the returned `pyrogram.Client`; the QR login is run
    by an internal Telethon client that takes its own settings. Silently
    dropping them would send the authorization out over a direct connection —
    and Telethon's `proxy` tuple would then be handed to Pyrogram, which wants
    a dict."""
    seen: dict = {}

    class FakeTelethon:
        UserId = USER_ID

        class session:  # noqa: N801 - mirrors Telethon's attribute layout
            dc_id = DC_ID

            class auth_key:  # noqa: N801
                key = DUMMY_KEY

        async def connect(self) -> None:
            pass

        async def disconnect(self) -> None:
            pass

    async def fake_to_telethon(self, **kwargs):
        seen.update(kwargs)
        return FakeTelethon()

    monkeypatch.setattr(Account, "ToTelethon", fake_to_telethon)

    tdesk = _build_tdesktop()
    telethon_proxy = ("socks5", "127.0.0.1", 9050)
    pyrogram_proxy = {"scheme": "socks5", "hostname": "127.0.0.1", "port": 9050}
    client = await tdesk.ToPyrogram(
        flag=CreateNewSession,
        telethon_kwargs={"proxy": telethon_proxy},
        proxy=pyrogram_proxy,
    )

    assert seen["proxy"] == telethon_proxy, "QR login must not go out unproxied"
    assert "telethon_kwargs" not in seen
    assert client.proxy == pyrogram_proxy

    await client.storage.open()
    try:
        assert await client.storage.auth_key() == DUMMY_KEY
    finally:
        await client.storage.close()

    # Keys ToPyrogram() fixes itself would otherwise blow up as a bare
    # "got multiple values for keyword argument" from a call the caller
    # never wrote.
    with pytest.raises(ValueError, match="telethon_kwargs"):
        await tdesk.ToPyrogram(
            flag=CreateNewSession, telethon_kwargs={"api": API.TelegramAndroid}
        )


async def test_to_pyrogram_rejects_invalid_flag() -> None:
    tdesk = _build_tdesktop()
    with pytest.raises(LoginFlagInvalid):
        await tdesk.mainAccount.ToPyrogram(flag=42)


async def test_to_pyrogram_accepts_custom_api_instance() -> None:
    """A generated (randomized) API still reaches the client verbatim."""
    api = API.TelegramAndroid.Generate(unique_id="pyrogram-test")
    assert isinstance(api, APIData)

    tdesk = _build_tdesktop()
    client = await tdesk.mainAccount.ToPyrogram(api=api)

    assert client.api_id == api.api_id
    assert client.device_model == api.device_model
    assert client.lang_pack == api.lang_pack


# === sessions tdata cannot represent ===


async def test_from_pyrogram_rejects_test_mode_session() -> None:
    """tdata written here always carries the production MTP config, so a
    test-DC auth key would be dead on arrival."""
    session_string = await pyro.export_session_string(
        api_id=API.TelegramDesktop.api_id,
        dc_id=DC_ID,
        auth_key=DUMMY_KEY,
        user_id=USER_ID,
        test_mode=True,
    )
    client = pyrogram.Client(
        "testdc",
        api_id=API.TelegramDesktop.api_id,
        api_hash=API.TelegramDesktop.api_hash,
        session_string=session_string,
        in_memory=True,
    )
    with pytest.raises(PyrogramSessionUnsupported):
        await TDesktop.FromPyrogram(client)


async def test_from_pyrogram_rejects_bot_session() -> None:
    """Telegram Desktop cannot sign in as a bot."""
    session_string = await pyro.export_session_string(
        api_id=API.TelegramDesktop.api_id,
        dc_id=DC_ID,
        auth_key=DUMMY_KEY,
        user_id=USER_ID,
        is_bot=True,
    )
    client = pyrogram.Client(
        "botsession",
        api_id=API.TelegramDesktop.api_id,
        api_hash=API.TelegramDesktop.api_hash,
        session_string=session_string,
        in_memory=True,
    )
    with pytest.raises(PyrogramSessionUnsupported):
        await TDesktop.FromPyrogram(client)


async def test_read_credentials_closes_storage_it_opened() -> None:
    """Leaving the SQLite connection open behind the caller's back leaks it —
    and Pyrogram's own connect() reopens the storage anyway."""
    tdesk = _build_tdesktop()
    client = await tdesk.mainAccount.ToPyrogram()

    await pyro.read_credentials(client)

    # Storage was not open before the call, so it must not be open after it:
    # a closed Pyrogram storage is a closed sqlite connection.
    with pytest.raises(sqlite3.ProgrammingError):
        await client.storage.dc_id()


async def test_read_credentials_leaves_caller_opened_storage_open() -> None:
    """...but a storage the caller opened stays open — closing it would break
    a live client mid-flight."""
    tdesk = _build_tdesktop()
    client = await tdesk.mainAccount.ToPyrogram()
    await client.storage.open()
    try:
        credentials = await pyro.read_credentials(client)
        assert credentials.auth_key == DUMMY_KEY
        assert await client.storage.dc_id() == DC_ID
    finally:
        await client.storage.close()
