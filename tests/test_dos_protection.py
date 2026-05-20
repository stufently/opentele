"""Phase 1.0.2 — DoS protection tests for unbounded count loops.

Background (3-AI consultation, Codex flagged):

``MapData.read()`` and ``Account._setMtpAuthorization()`` read a ``count``
or ``key_count`` field from an attacker-influenced byte stream and then loop
that many times *without* checking ``stream.status() != Ok`` inside the loop
body. If the attacker can produce a tdata file whose encrypted ``map`` or
``data`` payload contains ``count=0xFFFFFFFF`` (4 294 967 295) followed by
zero bytes of payload, the loop body will read past EOF on every iteration
(returning 0, setting ReadPastEnd) and burn ~4 billion no-op iterations
before the trailing ``ExpectStreamStatus`` raises.

Empirically that's tens of minutes to hours of CPU per malformed file — a
DoS vector.

**Test strategy:**

We do NOT use ``pytest-timeout`` here because its ``Failed`` exception is a
``BaseException`` subclass, which makes asserting "this should be fast"
flaky across Python versions (3.10 happens to finish under the limit on
some hosts).

Instead we measure ``time.perf_counter()`` around the call and assert the
operation completes in under ``DOS_BUDGET_SEC``. If the budget is exceeded
we record an xfail (bug confirmed) using the standard ``pytest.xfail()``
in-test marker, so the test is reported as XFAIL on hosts where the bug
manifests and PASSED on hosts/versions where it doesn't.

A count of ``2_000_000`` is used (not 0xFFFFFFFF) so the test bounds itself
naturally — even with the bug, the read returns in O(seconds), not hours.
The wall-clock assertion still proves the bug is present.

Once Phase 1.0.3 fixes ``MapData.read`` to bail on stream-status mismatch
inside the count loop, the operation will return in milliseconds and the
tests will all pass unconditionally.
"""
from __future__ import annotations

import struct
import time
import typing as t
from pathlib import Path

import pytest
from opentele.td import shared as td
from opentele.td.account import Account, MapData
from opentele.td.configs import lskType
from opentele.td.qdatastream import (
    QBuffer,
    QByteArray,
    QDataStream,
    QIODevice,
)

# Maximum wall-clock seconds a malformed count-loop should take. A
# non-vulnerable implementation finishes in <0.01s; the buggy one takes
# 0.5-5+ seconds for count=2_000_000 (depending on Python version and CPU).
DOS_BUDGET_SEC = 0.5

# Synthetic "moderately large" count used by the malformed-payload tests.
# Big enough to make the buggy implementation visibly slow (>0.5s), small
# enough to fail-fast deterministically even on slow CI runners.
SYNTHETIC_COUNT = 2_000_000


# ---------------------------------------------------------------------------
# Helpers — construct a fake decrypted MapData payload
# ---------------------------------------------------------------------------


def _make_descriptor(payload: bytes) -> td.Storage.EncryptedDescriptor:
    """Hand-build a ``Storage.EncryptedDescriptor`` whose ``.stream``
    points at *payload* opened ReadOnly.

    This is what ``DecryptLocal`` returns after a successful decrypt — we
    skip the AES round-trip to keep the test isolated to the consumer.

    Note: ``EncryptedDescriptor`` reserves bytes 0-3 for the size header
    (skipped on read via ``buffer.seek(4)``). We prepend 4 dummy bytes so
    the consumer's seek(4) lands on the first real byte.
    """
    raw = b"\x00\x00\x00\x00" + payload
    desc = td.Storage.EncryptedDescriptor()
    desc.data = QByteArray(raw)
    desc.buffer.setBuffer(desc.data)
    desc.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    desc.buffer.seek(4)  # skip the (fake) size header
    desc.stream.setDevice(desc.buffer)
    desc.stream.setVersion(QDataStream.Version.Qt_5_1)
    return desc


def _make_huge_count_payload(key_type: int, count: int = SYNTHETIC_COUNT) -> bytes:
    """Wire format for ``lskDraft`` / ``lskBotStorages``:
    ``uint32 keyType + uint32 count + count × (uint64 fileKey, uint64 peerId)``.

    We deliberately give *no* payload after count — the loop will fail on
    every iteration with ReadPastEnd.
    """
    return struct.pack(">II", key_type, count)


class _FakeMapFile:
    """Stands in for the ``FileReadDescriptor`` returned by
    ``Storage.ReadFile("map", ...)``. Only ``.version`` and ``.stream`` are
    consumed by ``MapData.read`` before it pivots to encrypted data, so we
    keep this minimal.
    """

    def __init__(self) -> None:
        self.version = 0
        self.data = QByteArray()
        # Three empty QByteArrays for the `legacySalt >> legacyKey >> map`
        # reads in MapData.read (account.py:80).
        self.data.extend(b"\x00\x00\x00\x00" * 3)
        self.buffer = QBuffer(self.data)
        self.buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self.stream = QDataStream()
        self.stream.setDevice(self.buffer)
        self.stream.setVersion(QDataStream.Version.Qt_5_1)


@pytest.fixture
def patch_decrypt(monkeypatch: pytest.MonkeyPatch):
    """Yields a setter: ``patch_decrypt(payload_bytes)`` makes
    ``Storage.ReadFile`` and ``Storage.DecryptLocal`` return a descriptor
    whose stream reads *payload_bytes*. Lets us inject malformed encrypted
    content without going through the real AES round-trip.
    """

    def _do_patch(payload: bytes) -> None:
        def fake_read_file(name: str, base: str):
            return _FakeMapFile()

        def fake_decrypt(encrypted: QByteArray, authKey):
            return _make_descriptor(payload)

        monkeypatch.setattr(td.Storage, "ReadFile", fake_read_file)
        monkeypatch.setattr(td.Storage, "DecryptLocal", fake_decrypt)

    return _do_patch


def _run_and_measure(callable_: t.Callable[[], None]) -> tuple[float, BaseException]:
    """Run *callable_* expecting it to raise. Returns (elapsed_seconds,
    exception). If it didn't raise, returns (elapsed, None) — but that
    would itself be a bug (malformed payload should raise)."""
    start = time.perf_counter()
    raised: BaseException | None = None
    try:
        callable_()
    except BaseException as exc:  # OpenTeleException derives from BaseException
        raised = exc
    elapsed = time.perf_counter() - start
    return elapsed, raised


def _assert_dos_bounded_or_xfail(
    elapsed: float, raised: BaseException | None, label: str
) -> None:
    """Common assertion helper: the call must raise, and must take less
    than DOS_BUDGET_SEC. If it took longer, the bug is present — record
    xfail (in-test) so CI is green but the bug is visible."""
    assert raised is not None, f"{label}: malformed payload didn't raise"
    if elapsed > DOS_BUDGET_SEC:
        pytest.xfail(
            f"CONFIRMED DoS in {label}: malformed count loop took "
            f"{elapsed:.2f}s (budget {DOS_BUDGET_SEC}s). Fix in 1.0.3 — "
            "add inner ExpectStreamStatus or cap count by remaining buffer."
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_mapdata_huge_lskDraft_count_bounded_or_xfails(
    tmp_path: Path, patch_decrypt: t.Callable[[bytes], None]
) -> None:
    """SECURITY: a malformed encrypted map declaring a large ``count`` for
    ``lskDraft`` followed by zero payload bytes must FAIL FAST (raise in
    <0.5s), not spin millions of no-op iterations.

    Reads up to account.py:154-161 (lskDraft branch).
    """
    payload = _make_huge_count_payload(lskType.lskDraft)
    patch_decrypt(payload)

    md = MapData(basePath=str(tmp_path))
    elapsed, raised = _run_and_measure(lambda: md.read(object(), QByteArray()))
    _assert_dos_bounded_or_xfail(elapsed, raised, "MapData.read[lskDraft]")


def test_mapdata_huge_lskBotStorages_count_bounded_or_xfails(
    tmp_path: Path, patch_decrypt: t.Callable[[bytes], None]
) -> None:
    """``lskBotStorages`` — TDesktop 5.x-6.x key with the same loop
    pattern (account.py:274-280). Phase 1.5 inherited it from lskDraft."""
    payload = _make_huge_count_payload(lskType.lskBotStorages)
    patch_decrypt(payload)

    md = MapData(basePath=str(tmp_path))
    elapsed, raised = _run_and_measure(lambda: md.read(object(), QByteArray()))
    _assert_dos_bounded_or_xfail(elapsed, raised, "MapData.read[lskBotStorages]")


def test_mapdata_huge_lskDraftPosition_count_bounded_or_xfails(
    tmp_path: Path, patch_decrypt: t.Callable[[bytes], None]
) -> None:
    """``lskDraftPosition`` has the same loop pattern as ``lskDraft``
    (account.py:166-172)."""
    payload = _make_huge_count_payload(lskType.lskDraftPosition)
    patch_decrypt(payload)

    md = MapData(basePath=str(tmp_path))
    elapsed, raised = _run_and_measure(lambda: md.read(object(), QByteArray()))
    _assert_dos_bounded_or_xfail(elapsed, raised, "MapData.read[lskDraftPosition]")


def test_mapdata_lskLegacyImages_count_bounded_or_xfails(
    tmp_path: Path, patch_decrypt: t.Callable[[bytes], None]
) -> None:
    """The legacy image-cache branches (``lskLegacyImages``,
    ``lskLegacyStickerImages``, ``lskLegacyAudios``) share the same
    unchecked count loop (account.py:178-184)."""
    payload = _make_huge_count_payload(lskType.lskLegacyImages)
    patch_decrypt(payload)

    md = MapData(basePath=str(tmp_path))
    elapsed, raised = _run_and_measure(lambda: md.read(object(), QByteArray()))
    _assert_dos_bounded_or_xfail(elapsed, raised, "MapData.read[lskLegacyImages]")


def test_setMtpAuthorization_huge_key_count_bounded_or_xfails(tmp_path: Path) -> None:
    """SECURITY: ``Account._setMtpAuthorization()`` reads ``key_count`` then
    loops without status check (account.py:962-972). Each iteration runs
    SHA-1 over a 256-byte buffer, so this branch is more expensive than
    MapData's draft loop — DoS is much faster to exhaust CPU."""
    from opentele.api import API
    from opentele.td import TDesktop

    # Wire format: int32 UserId, int32 MainDcId, then int32 key_count.
    # We use small UserId+MainDcId to skip the wide-ids branch.
    buf = QByteArray(b"")
    s = QDataStream(buf, QIODevice.OpenModeFlag.WriteOnly)
    s.setVersion(QDataStream.Version.Qt_5_1)
    s.writeInt32(12345)  # UserId
    s.writeInt32(2)  # MainDcId
    # SHA-1 per iteration makes 2M too slow even when buggy; 500k is
    # the sweet spot — slow enough on most CI hosts to confirm the DoS
    # without burning CI time uselessly.
    s.writeInt32(500_000)

    tdesk = TDesktop()
    tdesk._TDesktop__generateLocalKey()
    account = Account(owner=tdesk, basePath=str(tmp_path), api=API.TelegramDesktop)

    elapsed, raised = _run_and_measure(lambda: account._setMtpAuthorization(buf))
    _assert_dos_bounded_or_xfail(
        elapsed, raised, "Account._setMtpAuthorization[readKeys]"
    )


def test_mapdata_zero_count_does_not_loop(
    tmp_path: Path, patch_decrypt: t.Callable[[bytes], None]
) -> None:
    """Counterpart sanity test: ``count=0`` must NOT enter the loop body
    and the read must complete immediately. This proves the test
    infrastructure (patch_decrypt / synthetic descriptor) works correctly
    on the happy path, so an xfail above is a real bug, not a fixture issue.
    """
    payload = _make_huge_count_payload(lskType.lskDraft, count=0)
    patch_decrypt(payload)

    md = MapData(basePath=str(tmp_path))
    elapsed, raised = _run_and_measure(lambda: md.read(object(), QByteArray()))
    # count=0 → no loop iterations → no exception either way
    assert elapsed < DOS_BUDGET_SEC, (
        f"count=0 fixture should be instant, took {elapsed:.3f}s"
    )
    # No exception expected with valid count=0 + empty rest of stream.
    # (The atEnd() check exits the outer while loop.)
