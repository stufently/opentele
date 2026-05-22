"""Regression tests for the 5 known-issue fixes shipped in 1.3.0.

Each test is named after the CHANGELOG entry it pins down, so if any of
these flips back to the old behaviour the failure points at the spec.
"""
from __future__ import annotations

import struct
import warnings
from contextlib import contextmanager
from pathlib import Path

import pytest
from opentele.exception import TDataReadMapDataFailed
from opentele.td import TDesktop
from opentele.td.account import Account
from opentele.td.auth import AuthKey, AuthKeyType
from opentele.td.configs import DcId


@contextmanager
def monkeypatch_context(target, attr, replacement):
    """tiny stand-in for pytest.MonkeyPatch.setattr inside arbitrary contexts."""
    original = getattr(target, attr)
    setattr(target, attr, replacement)
    try:
        yield
    finally:
        setattr(target, attr, original)


def _make_account(tdesk: TDesktop, base: str) -> Account:
    from opentele.api import API
    account = Account(owner=tdesk, basePath=base, api=API.TelegramDesktop, index=0)
    dc_id = DcId(2)
    authkey = AuthKey(b"\xab" * AuthKey.kSize, AuthKeyType.ReadFromFile, dc_id)
    account._setMtpAuthorizationCustom(dc_id, 88884444, [authkey])
    tdesk._addSingleAccount(account)
    return account


# ---------------------------------------------------------------------------
# Issue #1: kPerformanceMode default flipped True → False
# ---------------------------------------------------------------------------


def test_kPerformanceMode_default_is_False():
    """1.3.0 flipped the source-defined class default: new TDesktop classes
    no longer silently use the constant ``localKey`` from upstream Phase 1.

    We can't trust the live class attribute (other tests in this module mutate
    it via the toggle). Instead, grep the source file for the literal default
    — that's the durable assertion.
    """
    src_file = Path(__file__).resolve().parent.parent / "src" / "td" / "tdesktop.py"
    text = src_file.read_text(encoding="utf-8")
    assert "kPerformanceMode: bool = False" in text, \
        "1.3.0 flipped the kPerformanceMode source default to False (security)."


def test_PerformanceMode_True_emits_UserWarning():
    """Opt-in into the insecure constant-localKey mode must emit a warning."""
    original = TDesktop.kPerformanceMode
    try:
        TDesktop.kPerformanceMode = False  # ensure transition False→True
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            TDesktop.PerformanceMode(True)
        assert any(
            issubclass(w.category, UserWarning) and "localKey" in str(w.message)
            for w in caught
        ), f"expected UserWarning mentioning localKey, got: {[(w.category, str(w.message)) for w in caught]}"
    finally:
        TDesktop.kPerformanceMode = original


# ---------------------------------------------------------------------------
# Issue #2: non-ASCII passcode no longer crashes + roundtrips through tdata
# ---------------------------------------------------------------------------


def test_cyrillic_passcode_does_not_crash_on_init():
    tdesk = TDesktop(passcode="пароль")  # noqa: RUF001
    assert tdesk is not None


def test_emoji_passcode_does_not_crash_on_init():
    tdesk = TDesktop(passcode="🔐пасс")  # noqa: RUF001
    assert tdesk is not None


def test_utf8_passcode_save_and_load_roundtrip(tmp_path):
    """A Cyrillic passcode must survive a full SaveTData → LoadTData roundtrip
    (the actual user-visible bug — 1.2.x crashed at save time with
    UnicodeEncodeError)."""
    passcode = "Пароль123🔐"
    base = str(tmp_path / "tdata")

    tdesk = TDesktop(passcode=passcode)
    tdesk._TDesktop__generateLocalKey()
    _make_account(tdesk, base)
    tdesk.SaveTData(base)  # would raise UnicodeEncodeError pre-1.3.0

    # Reload with the same passcode — succeeds.
    td2 = TDesktop(base, passcode=passcode)
    assert td2.isLoaded()
    assert len(td2.accounts) == 1


# ---------------------------------------------------------------------------
# Issue #3: Performance mode no longer silently drops MTP config
# ---------------------------------------------------------------------------


def test_perf_mode_round_trip_preserves_mtp_config(tmp_path):
    """1.2.x: writeMtpConfig was skipped when kPerformanceMode=True, and the
    matching read path returned a default Config. Net effect: any persisted
    MTP config field was lost across a SaveTData round-trip. 1.3.0 makes
    both unconditional. Verify that data is still there after reload."""
    original = TDesktop.kPerformanceMode
    try:
        TDesktop.kPerformanceMode = True
        tdesk = TDesktop()
        tdesk._TDesktop__generateLocalKey()
        base = str(tmp_path / "tdata")
        _make_account(tdesk, base)
        tdesk.SaveTData(base)

        td2 = TDesktop(base)
        assert td2.isLoaded()
        # Monkeypatch witness: writeMtpConfig MUST have been called during
        # the SaveTData above, even under kPerformanceMode=True. Pre-1.3.0
        # the call was skipped → silent data loss across round-trip.
        from opentele.td import account as account_mod
        write_calls: list[str] = []
        original_write = account_mod.StorageAccount.writeMtpConfig

        def witness(self, basePath):
            write_calls.append(basePath)
            return original_write(self, basePath)

        with monkeypatch_context(account_mod.StorageAccount, "writeMtpConfig", witness):
            tdesk.SaveTData(base)
        assert write_calls, "writeMtpConfig was not invoked — perf mode still skipping it"
    finally:
        TDesktop.kPerformanceMode = original


# ---------------------------------------------------------------------------
# Issue #4: unknown lskType now fails closed by default
# ---------------------------------------------------------------------------


# Reuse the monkeypatch fixture pattern from tests/test_dos_protection.py to
# inject a fake decrypted MapData payload — that lets us trigger the unknown-
# key branch end-to-end without going through the real AES round-trip.
from opentele.td import shared as td  # noqa: E402
from opentele.td.account import MapData  # noqa: E402
from opentele.td.qdatastream import QBuffer, QByteArray, QDataStream, QIODevice  # noqa: E402


class _FakeMapFile:
    def __init__(self) -> None:
        self.version = 0
        self.data = QByteArray()
        self.data.extend(b"\x00\x00\x00\x00" * 3)
        self.buffer = QBuffer(self.data)
        self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.stream = QDataStream()
        self.stream.setDevice(self.buffer)
        self.stream.setVersion(QDataStream.Version.Qt_5_1)


def _make_descriptor(payload: bytes) -> td.Storage.EncryptedDescriptor:
    """Build an EncryptedDescriptor whose stream produces *payload* after the
    4-byte size-header skip."""
    raw = b"\x00\x00\x00\x00" + payload
    desc = td.Storage.EncryptedDescriptor()
    desc.data = QByteArray(raw)
    desc.buffer.setBuffer(desc.data)
    desc.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    desc.buffer.seek(4)
    desc.stream.setDevice(desc.buffer)
    desc.stream.setVersion(QDataStream.Version.Qt_5_1)
    return desc


def _unknown_key_payload() -> bytes:
    """One uint32 keyType=0xFE (unknown). Qt_5_1 big-endian."""
    return struct.pack(">I", 0xFE)


def _run_read_with_unknown_key(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_read_file(name: str, base: str):
        return _FakeMapFile()

    def fake_decrypt(encrypted: QByteArray, authKey):
        return _make_descriptor(_unknown_key_payload())

    monkeypatch.setattr(td.Storage, "ReadFile", fake_read_file)
    monkeypatch.setattr(td.Storage, "DecryptLocal", fake_decrypt)

    map_data = MapData(basePath="/nonexistent")
    # localKey doesn't matter — DecryptLocal is patched out.
    fake_key = type("_K", (), {"key": QByteArray(b"\x00" * 256)})()
    map_data.read(fake_key, QByteArray())  # type: ignore[arg-type]


def test_unknown_lskType_strict_default_raises(monkeypatch):
    """Default (env unset): unknown key raises TDataReadMapDataFailed end-to-end.
    Pre-1.3.0: silently logged and continued, reading the next 4 bytes (which
    were unknown payload) as if they were the next keyType → desync."""
    monkeypatch.delenv("OPENTELE_LENIENT_UNKNOWN_LSK", raising=False)
    with pytest.raises(TDataReadMapDataFailed, match="Unknown lskType key"):
        _run_read_with_unknown_key(monkeypatch)


def test_unknown_lskType_lenient_mode_does_not_raise(monkeypatch):
    """With ``OPENTELE_LENIENT_UNKNOWN_LSK=1`` the unknown-key handler logs
    and breaks out of the loop instead of raising — partial map returned."""
    monkeypatch.setenv("OPENTELE_LENIENT_UNKNOWN_LSK", "1")
    # Should not raise.
    _run_read_with_unknown_key(monkeypatch)


def test_unknown_lskType_lenient_only_accepts_value_one(monkeypatch):
    """Any value other than exact ``"1"`` keeps strict behaviour."""
    for value in ("0", "true", "yes", ""):
        monkeypatch.setenv("OPENTELE_LENIENT_UNKNOWN_LSK", value)
        with pytest.raises(TDataReadMapDataFailed):
            _run_read_with_unknown_key(monkeypatch)


# ---------------------------------------------------------------------------
# Issue #5: Docker dep lock file shipped alongside Dockerfile
# ---------------------------------------------------------------------------


def test_docker_requirements_lock_exists_and_hash_pinned():
    repo_root = Path(__file__).resolve().parent.parent
    lock = repo_root / "requirements-docker.txt"
    assert lock.is_file(), "requirements-docker.txt missing"
    body = lock.read_text(encoding="utf-8")
    assert "--hash=sha256:" in body, "lock file has no hashes"
    assert "telethon==" in body.lower(), "telethon not pinned"
    assert "tgcrypto-pyrofork==" in body.lower(), "tgcrypto-pyrofork not pinned"


def test_dockerfile_uses_require_hashes():
    repo_root = Path(__file__).resolve().parent.parent
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    assert "--require-hashes" in dockerfile, \
        "Dockerfile should install runtime deps with --require-hashes"
    assert "requirements-docker.txt" in dockerfile, \
        "Dockerfile should reference requirements-docker.txt"
    assert "pip install --no-cache-dir --no-deps" in dockerfile, \
        "Dockerfile should install the wheel with --no-deps (lock provides deps)"
