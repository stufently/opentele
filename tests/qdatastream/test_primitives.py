"""Phase 4: QDataStream primitive byte-level coverage.

Эти golden bytes — **oracle** для Phase 5 pure-Python QDataStream rewrite.
Любое отклонение в bytes означает несовместимость с TDesktop форматом.

Источник истины: PyQt6 QDataStream Qt_5_1 (использует Qt 5.1 binary format —
большой endian, фиксированные размеры типов).
"""
from PyQt6.QtCore import QByteArray, QDataStream, QIODevice


def _writer():
    data = QByteArray()
    s = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
    s.setVersion(QDataStream.Version.Qt_5_1)
    return data, s


def _reader(data):
    s = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    s.setVersion(QDataStream.Version.Qt_5_1)
    return s


# === UInt32 ===


def test_writeUInt32_zero_golden() -> None:
    data, s = _writer()
    s.writeUInt32(0)
    assert bytes(data) == b"\x00\x00\x00\x00"


def test_writeUInt32_one_golden() -> None:
    data, s = _writer()
    s.writeUInt32(1)
    assert bytes(data) == b"\x00\x00\x00\x01"


def test_writeUInt32_cafebabe_big_endian() -> None:
    """Qt_5_1 — big-endian. 0xCAFEBABE → bytes [CA, FE, BA, BE]."""
    data, s = _writer()
    s.writeUInt32(0xCAFEBABE)
    assert bytes(data) == b"\xca\xfe\xba\xbe"


def test_writeUInt32_max_golden() -> None:
    data, s = _writer()
    s.writeUInt32(0xFFFFFFFF)
    assert bytes(data) == b"\xff\xff\xff\xff"


def test_uint32_roundtrip_boundary_values() -> None:
    for value in [0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFE, 0xFFFFFFFF]:
        data, s = _writer()
        s.writeUInt32(value)
        r = _reader(data)
        assert r.readUInt32() == value


# === UInt64 ===


def test_writeUInt64_one_golden() -> None:
    data, s = _writer()
    s.writeUInt64(1)
    assert bytes(data) == b"\x00\x00\x00\x00\x00\x00\x00\x01"


def test_writeUInt64_deadbeefcafebabe_big_endian() -> None:
    data, s = _writer()
    s.writeUInt64(0xDEADBEEFCAFEBABE)
    assert bytes(data) == b"\xde\xad\xbe\xef\xca\xfe\xba\xbe"


def test_writeUInt64_max_golden() -> None:
    data, s = _writer()
    s.writeUInt64(0xFFFFFFFFFFFFFFFF)
    assert bytes(data) == b"\xff" * 8


def test_uint64_roundtrip_boundary() -> None:
    for value in [
        0, 1,
        0x7FFFFFFFFFFFFFFF,  # signed max as unsigned
        0x8000000000000000,  # signed min boundary
        0xFFFFFFFFFFFFFFFE,
        0xFFFFFFFFFFFFFFFF,
    ]:
        data, s = _writer()
        s.writeUInt64(value)
        r = _reader(data)
        assert r.readUInt64() == value


# === UInt8 / UInt16 ===


def test_writeUInt8_golden() -> None:
    data, s = _writer()
    s.writeUInt8(0xAB)
    assert bytes(data) == b"\xab"


def test_writeUInt16_golden() -> None:
    data, s = _writer()
    s.writeUInt16(0xCAFE)
    assert bytes(data) == b"\xca\xfe"


def test_uint8_roundtrip() -> None:
    for value in [0, 1, 127, 128, 254, 255]:
        data, s = _writer()
        s.writeUInt8(value)
        r = _reader(data)
        assert r.readUInt8() == value


def test_uint16_roundtrip() -> None:
    for value in [0, 1, 0x7FFF, 0x8000, 0xFFFE, 0xFFFF]:
        data, s = _writer()
        s.writeUInt16(value)
        r = _reader(data)
        assert r.readUInt16() == value


# === Signed Int32 / Int64 ===


def test_writeInt32_negative_one_two_complement() -> None:
    """Negative ints stored as two's complement big-endian."""
    data, s = _writer()
    s.writeInt32(-1)
    assert bytes(data) == b"\xff\xff\xff\xff"


def test_int32_roundtrip_boundary() -> None:
    for value in [-(2**31), -1, 0, 1, 2**31 - 1]:
        data, s = _writer()
        s.writeInt32(value)
        r = _reader(data)
        assert r.readInt32() == value


def test_int64_roundtrip_boundary() -> None:
    for value in [-(2**63), -1, 0, 1, 2**63 - 1]:
        data, s = _writer()
        s.writeInt64(value)
        r = _reader(data)
        assert r.readInt64() == value


# === Multiple primitives in sequence ===


def test_mixed_writes_concatenate_in_order() -> None:
    """Stream writes append, not separate frames."""
    data, s = _writer()
    s.writeUInt32(0xAAAA1111)
    s.writeUInt64(0xBBBBBBBB22222222)
    s.writeUInt32(0xCCCC3333)

    expected = b"\xaa\xaa\x11\x11" + b"\xbb\xbb\xbb\xbb\x22\x22\x22\x22" + b"\xcc\xcc\x33\x33"
    assert bytes(data) == expected
    # Total length: 4 + 8 + 4 = 16
    assert len(bytes(data)) == 16


def test_mixed_reads_match_writes() -> None:
    data, s = _writer()
    s.writeUInt32(0xAAAA1111)
    s.writeUInt64(0xBBBBBBBB22222222)
    s.writeUInt32(0xCCCC3333)

    r = _reader(data)
    assert r.readUInt32() == 0xAAAA1111
    assert r.readUInt64() == 0xBBBBBBBB22222222
    assert r.readUInt32() == 0xCCCC3333
    assert r.atEnd()


# === Status semantics ===


def test_status_ok_on_empty_stream() -> None:
    data, s = _writer()
    assert s.status() == QDataStream.Status.Ok


def test_status_remains_ok_after_writes() -> None:
    data, s = _writer()
    s.writeUInt64(0x12345678)
    assert s.status() == QDataStream.Status.Ok


def test_status_ReadPastEnd_when_reading_empty() -> None:
    data = QByteArray()
    r = _reader(data)
    _ = r.readUInt32()  # читаем из пустого — должен fail
    assert r.status() == QDataStream.Status.ReadPastEnd
