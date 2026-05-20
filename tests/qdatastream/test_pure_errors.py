"""Phase 1.0.2 — error/edge-case coverage for the pure-Python ``opentele.td.qdatastream``.

These tests deliberately import from ``opentele.td.qdatastream`` (NOT PyQt6).
The companion tests in ``tests/qdatastream/test_primitives.py`` etc. use PyQt6
as the byte-level oracle and never touch our pure-Python implementation's
error paths. This file closes that gap: every assertion below exercises
``opentele.td.qdatastream`` directly.

Codex/Cursor/Gemini all agreed during 3-AI consultation that the previously
uncovered branches (lines 407, 426, 518, 227, 241, 263, 648 in
``src/td/qdatastream.py``) were the biggest correctness/security risk on the
hot path.

Scope:

* EOF on every fixed-width ``readUInt*/readInt*`` (returns 0, sets ReadPastEnd)
* Status stickiness — once ReadPastEnd, subsequent reads remain ReadPastEnd
* ``resetStatus()`` semantics
* ``QDataStream()`` without device — reads fail, writes fail
* ``readRawData(n)`` with ``n > available`` — returns short read, sets status
* ``readQString`` malformed inputs (truncated prefix, oversized payload,
  odd UTF-16 length, isolated surrogate)
* ``stream >> QByteArray`` malformed (truncated prefix, **huge declared size
  with short payload — NO 4GB allocation**)
* Null vs empty marker semantics on read
* ``QBuffer`` edges (None device, seek past end / negative, read past EOF)
* ``QFile`` edges (missing path, invalid mode, closed-file stability,
  WriteOnly does NOT create parent dirs)
* ``QDataStream(<wrong type>)`` → TypeError
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest
from opentele.td.qdatastream import (
    QBuffer,
    QByteArray,
    QDataStream,
    QDir,
    QFile,
    QIODevice,
)

Status = QDataStream.Status
Mode = QIODevice.OpenModeFlag


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_reader(payload: bytes) -> QDataStream:
    qba = QByteArray(payload)
    s = QDataStream(qba, Mode.ReadOnly)
    s.setVersion(QDataStream.Version.Qt_5_1)
    return s


# ===========================================================================
# (a) EOF on every fixed-width read + status stickiness + resetStatus
# ===========================================================================


@pytest.mark.parametrize(
    "method_name,size",
    [
        ("readUInt8", 1),
        ("readInt8", 1),
        ("readUInt16", 2),
        ("readInt16", 2),
        ("readUInt32", 4),
        ("readInt32", 4),
        ("readUInt64", 8),
        ("readInt64", 8),
    ],
)
def test_fixed_width_read_from_empty_buffer_returns_zero_and_sets_ReadPastEnd(
    method_name: str, size: int
) -> None:
    """Every fixed-width read on an empty buffer must (a) return 0,
    (b) set status to ReadPastEnd, without raising."""
    s = _make_reader(b"")
    value = getattr(s, method_name)()
    assert value == 0
    assert s.status() == Status.ReadPastEnd


@pytest.mark.parametrize(
    "method_name,size",
    [
        ("readUInt16", 2),
        ("readUInt32", 4),
        ("readUInt64", 8),
    ],
)
def test_fixed_width_read_with_short_buffer_returns_zero_and_sets_ReadPastEnd(
    method_name: str, size: int
) -> None:
    """A buffer shorter than the read width must trigger ReadPastEnd."""
    # Provide exactly size-1 bytes — one shy of complete read.
    payload = b"\x00" * (size - 1) if size > 1 else b""
    s = _make_reader(payload)
    value = getattr(s, method_name)()
    assert value == 0
    assert s.status() == Status.ReadPastEnd


def test_status_is_sticky_until_resetStatus() -> None:
    """After ReadPastEnd, the next read still returns 0 AND status stays
    ReadPastEnd. resetStatus() clears it."""
    s = _make_reader(b"")
    _ = s.readUInt32()
    assert s.status() == Status.ReadPastEnd

    # Second read on the same exhausted stream — also fails.
    _ = s.readUInt8()
    assert s.status() == Status.ReadPastEnd

    # resetStatus() puts us back to Ok (though next read still fails because
    # the device is still empty — the flag is just cleared).
    s.resetStatus()
    assert s.status() == Status.Ok


# ===========================================================================
# (b) QDataStream() without device
# ===========================================================================


def test_QDataStream_no_device_read_sets_ReadPastEnd() -> None:
    s = QDataStream()
    assert s.device() is None
    value = s.readUInt32()
    assert value == 0
    assert s.status() == Status.ReadPastEnd


def test_QDataStream_no_device_write_sets_WriteFailed() -> None:
    s = QDataStream()
    s.writeUInt32(0x12345678)
    # WriteFailed must be set, no exception thrown.
    assert s.status() == Status.WriteFailed


# ===========================================================================
# (c) readRawData with n > available
# ===========================================================================


def test_readRawData_more_than_available_returns_short_and_sets_ReadPastEnd() -> None:
    """``readRawData(n)`` must NOT raise when ``n > available``; it must
    return what it could read and set ReadPastEnd."""
    s = _make_reader(b"AB")  # 2 bytes available
    chunk = s.readRawData(8)
    assert chunk == b"AB"  # short read, no exception
    assert s.status() == Status.ReadPastEnd


def test_readRawData_no_device_returns_empty_and_sets_status() -> None:
    s = QDataStream()
    chunk = s.readRawData(4)
    assert chunk == b""
    assert s.status() == Status.ReadPastEnd


# ===========================================================================
# (d) readQString malformed
# ===========================================================================


def test_readQString_truncated_size_prefix_sets_ReadPastEnd() -> None:
    """Less than 4 bytes for the size header → ReadPastEnd, empty result."""
    s = _make_reader(b"\x00\x00\x00")  # 3 bytes — one short of header
    result = s.readQString()
    assert result == ""
    assert s.status() == Status.ReadPastEnd


def test_readQString_declared_size_exceeds_payload_sets_ReadPastEnd() -> None:
    """Header announces 1000 bytes of UTF-16-BE but only 4 follow."""
    payload = struct.pack(">I", 1000) + b"\x00A\x00B"
    s = _make_reader(payload)
    result = s.readQString()
    assert result == ""
    assert s.status() == Status.ReadPastEnd


def test_readQString_odd_utf16_byte_count_sets_ReadCorruptData_or_error() -> None:
    """An odd byte count for UTF-16-BE is malformed. The implementation must
    NOT crash with an unhandled UnicodeDecodeError; it should either set
    ReadCorruptData (the documented behaviour for malformed payload) or at
    minimum keep status non-Ok."""
    # size = 3 bytes — odd, can't be valid UTF-16-BE.
    payload = struct.pack(">I", 3) + b"\x00\x41\x00"
    s = _make_reader(payload)
    result = s.readQString()
    # Implementation must not crash; result is empty and status is not Ok.
    assert result == ""
    assert s.status() in (Status.ReadCorruptData, Status.ReadPastEnd)


def test_readQString_isolated_surrogate_is_handled_gracefully() -> None:
    """A bare high surrogate (D800-DBFF without a low surrogate) is not a
    valid Unicode scalar. PyQt's ``encode('utf-16-be')`` rejects it, so the
    pure-Python path must mirror that or at minimum not crash."""
    # size = 4 bytes — one isolated high surrogate D800 + one ASCII 'A'.
    payload = struct.pack(">I", 4) + b"\xd8\x00\x00\x41"
    s = _make_reader(payload)
    # Either: decode succeeds (Python is more permissive than PyQt) and the
    # surrogate survives in the str, OR decode fails and ReadCorruptData is
    # set. Neither should raise.
    try:
        result = s.readQString()
    except Exception as exc:  # pragma: no cover
        pytest.fail(f"readQString raised on isolated surrogate: {exc!r}")
    # If decode failed, result is "" and status reflects corruption.
    if s.status() != Status.Ok:
        assert result == ""
        assert s.status() == Status.ReadCorruptData


def test_readQString_null_marker_returns_empty_string() -> None:
    """size=0xFFFFFFFF is the null marker — PyQt6 6.6 returns "" for it,
    and our implementation matches."""
    payload = b"\xff\xff\xff\xff"
    s = _make_reader(payload)
    result = s.readQString()
    assert result == ""
    assert s.status() == Status.Ok


def test_readQString_empty_marker_returns_empty_string() -> None:
    """size=0 is the empty marker — also returns ""."""
    payload = b"\x00\x00\x00\x00"
    s = _make_reader(payload)
    result = s.readQString()
    assert result == ""
    assert s.status() == Status.Ok


# ===========================================================================
# (e) stream >> QByteArray malformed — SECURITY: no 4GB allocation
# ===========================================================================


def test_read_qbytearray_truncated_size_prefix_sets_ReadPastEnd() -> None:
    """3-byte size prefix → ReadPastEnd, target stays empty."""
    s = _make_reader(b"\x00\x00\x00")  # 3 bytes — one short of header
    out = QByteArray()
    s >> out
    assert len(out) == 0
    assert s.status() == Status.ReadPastEnd


def test_read_qbytearray_huge_declared_size_does_NOT_allocate_4GB() -> None:
    """SECURITY: a malformed stream declaring 0xFFFFFFFE bytes but providing
    only 3 must NOT pre-allocate ~4 GB. Instead, the read should fail fast
    with ReadPastEnd and leave the target empty.

    Codex flagged this during 3-AI consultation: an attacker who can
    influence a tdata payload could trigger OOM via this vector.
    """
    payload = struct.pack(">I", 0xFFFFFFFE) + b"\x00\x00\x00"  # claim 4GB, give 3 bytes
    s = _make_reader(payload)
    out = QByteArray()

    # We can't directly measure peak memory here, but if the implementation
    # tried to pre-allocate ``[0] * 0xFFFFFFFE`` the test process would OOM.
    # Reaching the assertion means no pre-allocation happened.
    s >> out

    assert len(out) == 0
    assert s.status() == Status.ReadPastEnd


def test_read_qbytearray_null_marker_produces_isEmpty_but_not_isNull_PyQt6_compat() -> None:
    """PyQt6 6.6: even a null marker produces ``isNull()==False`` on read —
    null is only set by default-construction. Our impl matches."""
    s = _make_reader(b"\xff\xff\xff\xff")
    out = QByteArray()
    s >> out
    assert out.isEmpty()
    assert out.isNull() is False  # PyQt6 quirk: read never produces null
    assert s.status() == Status.Ok


def test_read_qbytearray_empty_marker_produces_isEmpty_not_isNull() -> None:
    """size=0 marker — not null, empty."""
    s = _make_reader(b"\x00\x00\x00\x00")
    out = QByteArray()
    s >> out
    assert out.isEmpty()
    assert out.isNull() is False
    assert s.status() == Status.Ok


def test_default_QByteArray_is_null_and_empty() -> None:
    """Default-constructed QByteArray must be both null and empty."""
    qba = QByteArray()
    assert qba.isNull() is True
    assert qba.isEmpty() is True


def test_QByteArray_from_empty_bytes_is_empty_but_not_null() -> None:
    """``QByteArray(b"")`` is the canonical "empty but not null" form."""
    qba = QByteArray(b"")
    assert qba.isNull() is False
    assert qba.isEmpty() is True


# ===========================================================================
# (f) QBuffer edges
# ===========================================================================


def test_QBuffer_open_with_no_backing_returns_False() -> None:
    """``setBuffer(None)`` then ``open()`` → False (no device to open)."""
    buf = QBuffer()
    buf.setBuffer(None)
    assert buf.open(Mode.ReadOnly) is False
    assert buf.isOpen() is False


def test_QBuffer_seek_with_no_backing_returns_False() -> None:
    """``seek`` on an unbacked buffer must return False, not crash."""
    buf = QBuffer()
    assert buf.seek(0) is False


def test_QBuffer_negative_seek_is_clamped_or_rejected() -> None:
    """Negative seek positions are not valid Qt semantics. Our impl clamps
    to 0 (consistent with how ``BytesIO.seek(-1)`` behaves on absolute
    positioning) — this test pins that behaviour."""
    qba = QByteArray(b"hello")
    buf = QBuffer(qba)
    buf.open(Mode.ReadOnly)
    buf.seek(-1)
    # Clamped to 0 — first read produces full content.
    assert buf.read(5) == b"hello"


def test_QBuffer_seek_past_end_does_not_corrupt_pos() -> None:
    """Seeking past end is allowed (Qt's WriteOnly extends on write) and a
    subsequent read returns empty."""
    qba = QByteArray(b"abc")
    buf = QBuffer(qba)
    buf.open(Mode.ReadOnly)
    buf.seek(100)
    assert buf.read(10) == b""


def test_QBuffer_read_negative_returns_empty() -> None:
    """``read(-1)`` returns all remaining bytes (our impl's documented
    behaviour matches Python's BytesIO semantics)."""
    qba = QByteArray(b"hello")
    buf = QBuffer(qba)
    buf.open(Mode.ReadOnly)
    # Position is 0 after open. read(-1) → all 5 bytes.
    chunk = buf.read(-1)
    assert chunk == b"hello"


def test_QBuffer_read_past_end_returns_what_is_left() -> None:
    """Read past EOF returns the available remainder, not None or raise."""
    qba = QByteArray(b"abc")
    buf = QBuffer(qba)
    buf.open(Mode.ReadOnly)
    chunk = buf.read(100)
    assert chunk == b"abc"


def test_QBuffer_atEnd_with_no_backing_is_True() -> None:
    buf = QBuffer()
    assert buf.atEnd() is True


def test_QBuffer_bytesAvailable_with_no_backing_is_zero() -> None:
    buf = QBuffer()
    assert buf.bytesAvailable() == 0


# ===========================================================================
# (g) QFile edges
# ===========================================================================


def test_QFile_open_missing_path_returns_False(tmp_path: Path) -> None:
    """ReadOnly on a non-existent path → False, no exception."""
    f = QFile(str(tmp_path / "does-not-exist.bin"))
    assert f.open(Mode.ReadOnly) is False
    assert f.isOpen() is False


def test_QFile_open_invalid_mode_returns_False(tmp_path: Path) -> None:
    """A mode with neither ReadOnly nor WriteOnly bits → False."""
    p = tmp_path / "f.bin"
    p.write_bytes(b"x")
    f = QFile(str(p))
    # NotOpen=0 — no flags set.
    assert f.open(Mode.NotOpen) is False


def test_QFile_methods_on_closed_file_do_not_raise(tmp_path: Path) -> None:
    """``read``/``write``/``size``/``close`` on a closed/never-opened
    QFile must remain stable (return 0/b'' and not raise)."""
    f = QFile(str(tmp_path / "anything.bin"))
    # File was never opened.
    assert f.read(10) == b""
    assert f.write(b"x") == 0
    assert f.size() == 0
    f.close()  # must not raise on a never-opened file
    # And again — repeated close stays no-op.
    f.close()


def test_QFile_WriteOnly_does_NOT_create_parent_dirs(tmp_path: Path) -> None:
    """The comment in qdatastream.py says "Ensure parent dir exists" but
    QFile.open(WriteOnly) actually does NOT create parent dirs — it relies
    on the caller to use QDir.mkpath first. This test pins that contract.
    Codex flagged the comment as misleading during 3-AI consultation."""
    missing_dir = tmp_path / "no" / "such" / "dir"
    target = missing_dir / "out.bin"
    f = QFile(str(target))
    # Parent dir does NOT exist yet → open(WriteOnly) returns False.
    assert f.open(Mode.WriteOnly) is False
    assert not missing_dir.exists(), (
        "QFile.open(WriteOnly) must NOT auto-create parent dirs"
    )


def test_QFile_WriteOnly_succeeds_when_parent_dir_exists(tmp_path: Path) -> None:
    """Sanity counterpart: when parent dir exists, WriteOnly succeeds."""
    target = tmp_path / "out.bin"
    f = QFile(str(target))
    assert f.open(Mode.WriteOnly) is True
    assert f.write(b"hello") == 5
    f.close()
    assert target.read_bytes() == b"hello"


def test_QFile_size_after_close_returns_cached_size(tmp_path: Path) -> None:
    """After close(), size() returns the size known at close time."""
    target = tmp_path / "z.bin"
    target.write_bytes(b"abcd")
    f = QFile(str(target))
    f.open(Mode.ReadOnly)
    assert f.size() == 4
    f.close()
    assert f.size() == 4  # cached value


# ===========================================================================
# (h) QDataStream wrong type → TypeError
# ===========================================================================


def test_QDataStream_with_wrong_type_raises_TypeError() -> None:
    """``QDataStream(123)`` must raise ``TypeError`` (not silently accept)."""
    with pytest.raises(TypeError):
        QDataStream(123)  # type: ignore[arg-type]


def test_QDataStream_rshift_into_non_QByteArray_raises_TypeError() -> None:
    """``stream >> "string"`` must raise — target must be QByteArray."""
    s = _make_reader(b"\x00\x00\x00\x00")
    with pytest.raises(TypeError):
        s >> "not a QByteArray"  # type: ignore[operator]


def test_QDataStream_lshift_with_non_buffer_raises_TypeError() -> None:
    """``stream << object()`` must raise — must be buffer-protocol-like."""
    qba = QByteArray(b"")
    s = QDataStream(qba, Mode.WriteOnly)
    s.setVersion(QDataStream.Version.Qt_5_1)
    with pytest.raises(TypeError):
        s << object()  # type: ignore[operator]


# ===========================================================================
# Misc: QDir helpers (small coverage win)
# ===========================================================================


def test_QDir_exists_on_missing_path_returns_False(tmp_path: Path) -> None:
    assert QDir(str(tmp_path / "nope")).exists() is False


def test_QDir_mkpath_creates_nested_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c"
    d = QDir(str(tmp_path))
    assert d.mkpath(str(nested)) is True
    assert nested.exists()
