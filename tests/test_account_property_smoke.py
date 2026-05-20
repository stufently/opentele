"""Phase 1.0.2 — Account property smoke coverage.

Closes the uncovered trivial getter/setter lines in ``src/td/account.py``
(842, 846-847, 854, 884, 891) flagged by 3-AI consultation. These are pure
property accessors with no behaviour beyond field delegation, but they were
never exercised by the existing roundtrip tests.

We reuse the ``_build_tdesktop_with_dummy_account`` helper pattern from
``tests/mapdata/test_real_roundtrip.py`` so the constructed account is the
same shape as the one produced by the real save/load path.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from opentele.api import API
from opentele.td import TDesktop
from opentele.td import shared as td
from opentele.td.account import Account
from opentele.td.auth import AuthKeyType
from opentele.td.configs import DcId
from opentele.td.mtp import MTP


def _make_dummy_authkey(dc_id: int = 2) -> td.AuthKey:
    return td.AuthKey(
        b"\xAB" * td.AuthKey.kSize,
        AuthKeyType.ReadFromFile,
        DcId(dc_id),
    )


@pytest.fixture
def account_with_dummy_auth(tmp_path: Path) -> Account:
    """Build a fully-loaded Account (passes ``isLoaded()``) ready for
    property access tests."""
    base = str(tmp_path / "tdata")
    tdesk = TDesktop()
    tdesk._TDesktop__generateLocalKey()

    account = Account(owner=tdesk, basePath=base, api=API.TelegramDesktop, index=0)
    dc_id = DcId(2)
    user_id = 7654321
    authkey = _make_dummy_authkey(dc_id=int(dc_id))
    account._setMtpAuthorizationCustom(dc_id, user_id, [authkey])
    tdesk._addSingleAccount(account)
    return account


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_account_keyFile_getter_returns_string(account_with_dummy_auth: Account) -> None:
    """account.py:842 — ``keyFile`` getter returns a non-empty string
    (default ``"data"``)."""
    assert isinstance(account_with_dummy_auth.keyFile, str)
    # Default per TDesktop.kDefaultKeyFile
    assert account_with_dummy_auth.keyFile == "data"


def test_account_keyFile_setter_propagates_to_local_storage(
    account_with_dummy_auth: Account,
) -> None:
    """account.py:846-847 — assigning to ``keyFile`` updates both the
    Account's ``__keyFile`` and the underlying ``StorageAccount.keyFile``
    via ``Storage.ComposeDataString(value, index)``."""
    account = account_with_dummy_auth
    account.keyFile = "custom_key"
    assert account.keyFile == "custom_key"
    # The local StorageAccount must reflect the change. ComposeDataString
    # with index=0 returns the raw name (no "#N" suffix).
    assert account._local.keyFile == "custom_key"


def test_account_keyFile_setter_with_nonzero_index_adds_suffix(
    tmp_path: Path,
) -> None:
    """ComposeDataString appends ``#{index+1}`` for index > 0 — verify
    the setter passes index through correctly."""
    base = str(tmp_path / "tdata")
    tdesk = TDesktop()
    tdesk._TDesktop__generateLocalKey()

    account = Account(owner=tdesk, basePath=base, api=API.TelegramDesktop, index=2)
    dc_id = DcId(2)
    authkey = _make_dummy_authkey(dc_id=int(dc_id))
    account._setMtpAuthorizationCustom(dc_id, 999, [authkey])
    tdesk._addSingleAccount(account)

    account.keyFile = "alt"
    # index=2 → suffix "#3"
    assert account._local.keyFile == "alt#3"


def test_account_localKey_getter_and_setter(
    account_with_dummy_auth: Account,
) -> None:
    """account.py:854 — localKey getter/setter delegates to ``_local``."""
    account = account_with_dummy_auth
    # After _addSingleAccount, owner.localKey is propagated.
    original = account.localKey
    assert original is not None

    # Setter updates both the Account and the underlying StorageAccount.
    new_key = _make_dummy_authkey(dc_id=3)
    account.localKey = new_key
    assert account.localKey is new_key
    assert account._local.localKey is new_key


def test_account_MtpConfig_returns_local_config(
    account_with_dummy_auth: Account,
) -> None:
    """account.py:884 — MtpConfig property returns ``_local.config``."""
    config = account_with_dummy_auth.MtpConfig
    assert config is not None
    assert isinstance(config, MTP.Config)


def test_account_isAuthorized_returns_bool(
    account_with_dummy_auth: Account,
) -> None:
    """account.py:891 — isAuthorized() returns a bool. After
    _setMtpAuthorizationCustom (no real Telegram auth), isAuthorized is
    False — but the method must still be callable and return a bool."""
    result = account_with_dummy_auth.isAuthorized()
    assert isinstance(result, bool)
    # The dummy auth path sets isLoaded=True but NOT isAuthorized=True
    # (that requires a real session start), so we expect False.
    assert result is False
    # isLoaded must be True since _setMtpAuthorizationCustom succeeded.
    assert account_with_dummy_auth.isLoaded() is True
