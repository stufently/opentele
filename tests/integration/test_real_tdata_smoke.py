"""Real-tdata smoke test — read-only, no Telegram connect.

This is an **opt-in** integration test: it only runs if the env var
``OPENTELE_REAL_TDATA_PATH`` points to a usable Telegram Desktop ``tdata``
folder on disk. Otherwise pytest skips the whole module. CI does not set
the env var so this never runs in the matrix — it's meant for local
verification that pure-Python ``opentele.td.qdatastream`` (Phase 5) is
byte-compatible with real upstream-produced tdata.

Why not bundle a tdata fixture in the repo?

- A real ``tdata`` folder contains an MTProto ``auth_key`` (256 bytes) plus
  the user's Telegram session state. Anyone with that file can log in as
  the account. Bundling it would leak credentials.
- Production tdata varies in lskType key set (some accounts have
  ``_webviewStorageTokens`` non-empty, some don't; some have
  ``_botStoragesMap``, etc.) — a single fixture wouldn't cover the matrix
  anyway.

Usage::

    OPENTELE_REAL_TDATA_PATH=/path/to/tdata pytest tests/integration/test_real_tdata_smoke.py

The test loads a working copy (so the source folder stays unmodified),
verifies that ``TDesktop.LoadTData`` succeeds without PyQt6 in
``sys.modules``, and that core ``MapData`` fields parse to plausible types.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest
from opentele.td import TDesktop

_REAL_TDATA = os.environ.get("OPENTELE_REAL_TDATA_PATH")


pytestmark = pytest.mark.skipif(
    not _REAL_TDATA or not Path(_REAL_TDATA).is_dir(),
    reason=(
        "OPENTELE_REAL_TDATA_PATH not set or not a directory; opt-in test "
        "for verifying pure-Python QDataStream against real tdata."
    ),
)


@pytest.fixture
def working_tdata(tmp_path: Path) -> Path:
    """Copy the real tdata to a tmp_path so the test cannot mutate the source."""
    src = Path(_REAL_TDATA)  # type: ignore[arg-type]
    dst = tmp_path / "tdata"
    shutil.copytree(src, dst)
    return dst


def test_real_tdata_loads_without_pyqt6_runtime(working_tdata: Path) -> None:
    """Pure-Python qdatastream (Phase 5) handles production tdata without
    importing PyQt6 at runtime."""
    assert "PyQt6" not in sys.modules, (
        "PyQt6 must not be loaded before TDesktop import (Phase 5 USP)"
    )

    tdesk = TDesktop(basePath=str(working_tdata))

    assert tdesk.isLoaded()
    assert tdesk.accountsCount >= 1
    assert tdesk.mainAccount is not None
    # Production tdata always has a valid DC; sanity check it's a known DC.
    assert int(tdesk.mainAccount.MainDcId) in {1, 2, 3, 4, 5}
    # UserId is a positive int (uint64 in MTProto).
    assert tdesk.mainAccount.UserId > 0

    # Phase 5 invariant: parsing the tdata must NOT have pulled in PyQt6.
    assert "PyQt6" not in sys.modules, (
        "PyQt6 leaked into sys.modules during TDesktop.LoadTData — Phase 5 "
        "rewire is incomplete somewhere."
    )


def test_real_tdata_mapdata_has_phase15_keys_attributes(working_tdata: Path) -> None:
    """All Phase 1.5 new attributes are present on MapData after a real load."""
    tdesk = TDesktop(basePath=str(working_tdata))
    md = tdesk.mainAccount.MapData

    # Phase 1.5 keys (may be zero if upstream tdata didn't write them, but the
    # attributes must exist — proves the new lskType branches survived parse).
    assert hasattr(md, "_roundPlaceholder")
    assert hasattr(md, "_inlineBotsDownloads")
    assert hasattr(md, "_mediaLastPlaybackPositions")
    assert hasattr(md, "_botStoragesMap")
    assert hasattr(md, "_prefsKey")

    # Phase 1.5 lskWebviewTokens type fix: QByteArray (not raw int)
    qba = md._webviewStorageTokenBots
    assert hasattr(qba, "isEmpty"), (
        f"_webviewStorageTokenBots should be QByteArray-like, got {type(qba).__name__}"
    )
    assert hasattr(qba, "size")


def test_real_tdata_account_signature_intact(working_tdata: Path) -> None:
    """Loaded Account exposes the canonical attributes used by the bridge."""
    tdesk = TDesktop(basePath=str(working_tdata))
    acc = tdesk.mainAccount

    assert acc.isLoaded()
    assert isinstance(acc.UserId, int)
    assert int(acc.MainDcId) > 0
    # Account has the auth-key plumbing wired (would be needed by ToTelethon()).
    # We do NOT call ToTelethon() to avoid any network-side effect; just probe.
    assert hasattr(acc, "authKey"), "Account.authKey must be exposed"
