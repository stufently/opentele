"""Phase 1.0.2 — TDesktop lifecycle coverage.

Closes the uncovered lines in ``src/td/tdesktop.py`` flagged by 3-AI
consultation (354-376 = passcode path in ``__generateLocalKey``,
461-462 = active index branch in ``__loadFromTData``, 641 =
``PerformanceMode`` setter, 678 = ``api`` setter propagation,
721 = ``AppVersion`` property).

These are end-to-end tests using the real ``SaveTData``/``LoadTData`` flow
on disk, building accounts via the same helper that ``test_real_roundtrip``
uses (dummy AuthKey, no live Telegram).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from opentele.api import API
from opentele.exception import TDataBadDecryptKey
from opentele.td import TDesktop
from opentele.td import shared as td
from opentele.td.account import Account
from opentele.td.auth import AuthKeyType
from opentele.td.configs import DcId


def _make_dummy_authkey(dc_id: int = 2) -> td.AuthKey:
    return td.AuthKey(
        b"\xAB" * td.AuthKey.kSize,
        AuthKeyType.ReadFromFile,
        DcId(dc_id),
    )


def _build_tdesktop_with_dummy_account(
    base_path: str, passcode: str = None
) -> TDesktop:
    """Build TDesktop + dummy Account ready for ``SaveTData``.

    If passcode is provided, the client must be saved with that passcode
    and the localKey is generated via the non-performance-mode path
    (tdesktop.py:354-376), exercising salt + key derivation.
    """
    tdesk = TDesktop(passcode=passcode) if passcode else TDesktop()
    tdesk._TDesktop__generateLocalKey()

    account = Account(owner=tdesk, basePath=base_path, api=API.TelegramDesktop, index=0)
    dc_id = DcId(2)
    user_id = 88884444
    authkey = _make_dummy_authkey(dc_id=int(dc_id))
    account._setMtpAuthorizationCustom(dc_id, user_id, [authkey])
    tdesk._addSingleAccount(account)
    return tdesk


# ---------------------------------------------------------------------------
# PerformanceMode toggle
# ---------------------------------------------------------------------------


def test_PerformanceMode_toggle_false_then_true_persists_flag() -> None:
    """tdesktop.py:641 — PerformanceMode(False) flips ``kPerformanceMode``
    class attribute to False; PerformanceMode(True) flips it back.

    kPerformanceMode is a CLASS attribute, so test order matters: we save
    the original, exercise both branches, and restore at the end.
    """
    original = TDesktop.kPerformanceMode
    try:
        TDesktop.PerformanceMode(False)
        assert TDesktop.kPerformanceMode is False
        TDesktop.PerformanceMode(True)
        assert TDesktop.kPerformanceMode is True
    finally:
        TDesktop.kPerformanceMode = original


def test_PerformanceMode_default_argument_is_True() -> None:
    """``PerformanceMode()`` with no args enables it (default=True)."""
    original = TDesktop.kPerformanceMode
    try:
        TDesktop.PerformanceMode(False)
        assert TDesktop.kPerformanceMode is False
        TDesktop.PerformanceMode()  # default True
        assert TDesktop.kPerformanceMode is True
    finally:
        TDesktop.kPerformanceMode = original


# ---------------------------------------------------------------------------
# api setter propagation to accounts
# ---------------------------------------------------------------------------


def test_api_setter_propagates_to_existing_accounts(tmp_path: Path) -> None:
    """tdesktop.py:678 — assigning ``tdesk.api = X`` walks ``self.accounts``
    and sets ``account.api = X`` on each. With one account configured,
    the change must propagate."""
    base = str(tmp_path / "tdata_api")
    tdesk = _build_tdesktop_with_dummy_account(base)

    original = tdesk.mainAccount.api
    new_api = API.TelegramAndroid

    tdesk.api = new_api
    # Both the client and the account now report the new API class.
    assert tdesk.api is new_api
    assert tdesk.mainAccount.api is new_api
    # And it's different from the starting value (sanity).
    assert new_api is not original


# ---------------------------------------------------------------------------
# AppVersion property
# ---------------------------------------------------------------------------


def test_AppVersion_is_None_before_LoadTData(tmp_path: Path) -> None:
    """``__AppVersion`` is set only inside ``__loadFromTData`` — before
    a load it stays None."""
    tdesk = TDesktop()
    assert tdesk.AppVersion is None


def test_AppVersion_is_set_after_LoadTData(tmp_path: Path) -> None:
    """tdesktop.py:721 — after a successful LoadTData, ``AppVersion``
    holds the integer version stamp read from the key file."""
    base = str(tmp_path / "tdata_appver")
    tdesk = _build_tdesktop_with_dummy_account(base)
    tdesk.SaveTData(base)

    loaded = TDesktop(basePath=base)
    assert loaded.AppVersion is not None
    assert isinstance(loaded.AppVersion, int)
    # APP_VERSION in opentele is a non-zero positive integer.
    assert loaded.AppVersion > 0


# ---------------------------------------------------------------------------
# Passcode-protected save/load — exercises tdesktop.py:354-376
# ---------------------------------------------------------------------------


def test_passcode_protected_save_and_load_roundtrip(tmp_path: Path) -> None:
    """tdesktop.py:354-376 — saving with a passcode exercises the
    non-performance-mode key generation branch (salt + derived key from
    passcode bytes).

    Saving with passcode "1234" then loading with "1234" must succeed and
    produce a loaded client with the original account."""
    base = str(tmp_path / "tdata_pass")
    # Build WITH a passcode so kPerformanceMode is disabled internally.
    tdesk = _build_tdesktop_with_dummy_account(base, passcode="1234")
    tdesk.SaveTData(base, passcode="1234")

    # Load with the correct passcode.
    loaded = TDesktop(basePath=base, passcode="1234")
    assert loaded.isLoaded()
    assert loaded.accountsCount == 1
    assert loaded.mainAccount.UserId == 88884444


def test_passcode_wrong_password_raises_TDataBadDecryptKey(tmp_path: Path) -> None:
    """Loading a passcode-encrypted tdata with the WRONG passcode must
    raise ``TDataBadDecryptKey``. Confirms the passcode path actually
    encrypts (i.e. wrong password fails — proves it wasn't a no-op)."""
    base = str(tmp_path / "tdata_pass_wrong")
    tdesk = _build_tdesktop_with_dummy_account(base, passcode="correct")
    tdesk.SaveTData(base, passcode="correct")

    with pytest.raises(TDataBadDecryptKey):
        TDesktop(basePath=base, passcode="WRONG_PASSCODE")
