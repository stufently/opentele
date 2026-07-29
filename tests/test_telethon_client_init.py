"""Credential plumbing in ``opentele.tl.TelegramClient.__init__``.

Our ``__init__`` inserts an extra ``api`` parameter in slot 2, so a plain
Telethon-style positional call ``TelegramClient(session, api_id, api_hash)``
arrives as ``api=<api_id>, api_id=<api_hash>, api_hash=None`` and has to be
un-shifted. Upstream opentele did that with

    api_id = api
    api_hash = api_id

— the second line reads the name it just overwrote, so ``api_hash`` silently
became the *api_id*. Nothing complains at construction time and
``initConnection`` does not carry ``api_hash``, so an already-authorized
session behaves normally; only login RPCs (``send_code_request`` / ``sign_in``
/ ``start``) blow up, with ``ApiIdInvalidError``.

The library's own docstrings (``Account.FromTelethon``) advertise the
positional form, so this is the documented calling convention — it must
produce the same client as the keyword form.
"""
from __future__ import annotations

import json

import pytest
from opentele.api import API
from opentele.tl import TelegramClient
from telethon.crypto import AuthKey
from telethon.sessions import MemorySession, StringSession

REAL_ID = 2040
REAL_HASH = "b18441a1ff607e10a989891a5462e627"


def test_positional_api_id_and_hash_are_not_shifted():
    """``TelegramClient(session, api_id, api_hash)`` — the Telethon signature."""
    client = TelegramClient(MemorySession(), REAL_ID, REAL_HASH)
    assert client.api_id == REAL_ID
    assert client.api_hash == REAL_HASH


def test_positional_matches_keyword_form():
    positional = TelegramClient(MemorySession(), REAL_ID, REAL_HASH)
    keyword = TelegramClient(MemorySession(), api_id=REAL_ID, api_hash=REAL_HASH)
    assert (positional.api_id, positional.api_hash) == (keyword.api_id, keyword.api_hash)


def test_api_hash_is_never_the_api_id():
    """Direct canary for the self-assignment bug."""
    client = TelegramClient(MemorySession(), REAL_ID, REAL_HASH)
    assert client.api_hash != client.api_id
    assert isinstance(client.api_hash, str)


def test_api_id_as_string_still_pairs_with_its_hash():
    """Some callers pass the id as a string; the pairing must survive."""
    client = TelegramClient(MemorySession(), str(REAL_ID), REAL_HASH)
    assert str(client.api_id) == str(REAL_ID)
    assert client.api_hash == REAL_HASH


def test_positional_id_with_keyword_hash():
    """``TelegramClient(session, api_id, api_hash="...")``.

    Telethon marks everything after ``api_hash`` keyword-only, so this mix is a
    valid Telethon call. Only the id gets shifted into our ``api`` slot; the
    hash already landed in its own parameter. Before 1.3.2 the un-shift branch
    required a truthy ``api_id``, so this fell through with ``api_id=0`` and
    died in Telethon with "Your API ID or Hash cannot be empty or None".
    """
    client = TelegramClient(MemorySession(), REAL_ID, api_hash=REAL_HASH)
    assert client.api_id == REAL_ID
    assert client.api_hash == REAL_HASH


def test_ambiguous_positional_arguments_raise():
    """``TelegramClient(session, <int>, x, y)`` cannot be read coherently.

    Telethon has no fourth positional parameter, so this only happens when the
    caller thinks slot 2 is ``api_id``. Keeping all three values is impossible;
    silently dropping one would hand Telegram the wrong credentials, so it
    fails loudly.
    """
    with pytest.raises(TypeError, match="ambiguous positional arguments"):
        TelegramClient(MemorySession(), REAL_ID, REAL_HASH, "extra")


@pytest.mark.parametrize(
    "api",
    [API.TelegramDesktop, API.TelegramAndroid, API.TelegramIOS, API.TelegramMacOS],
)
def test_apidata_form_unaffected(api):
    """The ``api=APIData`` path must keep working unchanged."""
    client = TelegramClient(MemorySession(), api=api)
    assert client.api_id == api.api_id
    assert client.api_hash == api.api_hash


def test_default_api_is_telegram_desktop():
    client = TelegramClient(MemorySession())
    assert client.api_id == API.TelegramDesktop.api_id
    assert client.api_hash == API.TelegramDesktop.api_hash


# ---------------------------------------------------------------------------
# FromBundle — same credential plumbing, both session flavours.
#
# The network is stubbed out: FromBundle's only I/O is `connect()` +
# `is_user_authorized()`, and what we are pinning is what ends up in
# `client.api_id` / `client.api_hash`, not the RPC.
# ---------------------------------------------------------------------------


@pytest.fixture
def offline_client(monkeypatch):
    """Make ``connect()`` a no-op and ``is_user_authorized()`` return True."""

    async def _connect(self):
        return None

    async def _authorized(self):
        return True

    monkeypatch.setattr(TelegramClient, "connect", _connect, raising=False)
    monkeypatch.setattr(TelegramClient, "is_user_authorized", _authorized, raising=False)


def _write_bundle(tmp_path, payload):
    path = tmp_path / "acct.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


async def test_from_bundle_string_session_keeps_credentials(tmp_path, offline_client):
    """String-session branch: the JSON's app_hash must survive as api_hash."""
    # `StringSession().save()` on a fresh session returns "" (falsy), which
    # would send FromBundle down the .session-file branch instead — the string
    # needs a DC and an auth key to serialize to anything.
    stub = StringSession()
    stub.set_dc(2, "149.154.167.51", 443)
    stub.auth_key = AuthKey(b"\x00" * 256)
    session_string = stub.save()
    assert session_string, "fixture must produce a non-empty string session"

    bundle = _write_bundle(
        tmp_path,
        {"app_id": REAL_ID, "app_hash": REAL_HASH, "string_session": session_string},
    )

    client = await TelegramClient.FromBundle(bundle)
    assert client.api_id == REAL_ID
    assert client.api_hash == REAL_HASH


async def test_from_bundle_session_file_keeps_credentials(tmp_path, offline_client):
    """SQLite-session branch: same assertion, different constructor call site."""
    (tmp_path / "acct.session").touch()
    bundle = _write_bundle(tmp_path, {"app_id": REAL_ID, "app_hash": REAL_HASH})

    client = await TelegramClient.FromBundle(bundle)
    try:
        assert client.api_id == REAL_ID
        assert client.api_hash == REAL_HASH
    finally:
        # `connect` is stubbed, so nothing else will close the sqlite handle
        # this branch opened — without this the run emits a ResourceWarning.
        client.session.close()


async def test_from_bundle_rejects_missing_credentials(tmp_path, offline_client):
    bundle = _write_bundle(tmp_path, {"app_id": REAL_ID})
    with pytest.raises(ValueError, match="app_id/app_hash"):
        await TelegramClient.FromBundle(bundle)


async def test_from_bundle_rejects_missing_session_file(tmp_path, offline_client):
    bundle = _write_bundle(tmp_path, {"app_id": REAL_ID, "app_hash": REAL_HASH})
    with pytest.raises(FileNotFoundError, match=".session"):
        await TelegramClient.FromBundle(bundle)
