"""Phase 4.5 (review fix): readRawData / writeRawData goldens + QDataStream(QByteArray) ctor.

Codex Phase 4 review нашёл пропуск: rawData методы используются в src/td/auth.py,
src/td/account.py, src/td/mtp.py — но не были покрыты goldens. Phase 5 pure-Python
rewrite должен дать byte-identical output и для них.
"""
from PyQt6.QtCore import QByteArray, QDataStream, QIODevice


def _writer():
    data = QByteArray()
    s = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
    s.setVersion(QDataStream.Version.Qt_5_1)
    return data, s


# === writeRawData: write bytes as-is, no size prefix ===


def test_writeRawData_short_no_prefix() -> None:
    """writeRawData(bytes) пишет bytes как есть, без 4-byte length prefix
    (в отличие от <<QByteArray)."""
    data, s = _writer()
    s.writeRawData(b"hello")
    raw = bytes(data)
    assert raw == b"hello", (
        f"writeRawData must write bytes as-is (no prefix). Got: {raw!r}"
    )


def test_writeRawData_binary_payload() -> None:
    """Бинарные данные сохраняются дословно."""
    payload = b"\x00\xff\x01\xfe\x02\xfd\x80\x7f"
    data, s = _writer()
    s.writeRawData(payload)
    assert bytes(data) == payload


def test_writeRawData_empty_payload() -> None:
    """Пустой write — стрим без изменений."""
    data, s = _writer()
    s.writeRawData(b"")
    assert bytes(data) == b""


def test_writeRawData_long_4096_bytes() -> None:
    """4KB payload пишется целиком."""
    payload = bytes(range(256)) * 16  # 4096 bytes
    data, s = _writer()
    s.writeRawData(payload)
    assert bytes(data) == payload


# === readRawData: read N bytes verbatim ===


def test_readRawData_returns_exact_count() -> None:
    """readRawData(n) возвращает ровно n bytes."""
    data = QByteArray(b"hello world")
    r = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    r.setVersion(QDataStream.Version.Qt_5_1)
    out = r.readRawData(5)
    # PyQt6 readRawData может возвращать bytes или QByteArray —
    # обернём в bytes для совместимости.
    assert bytes(out) == b"hello"


def test_readRawData_consumes_bytes_advancing_stream() -> None:
    """После readRawData(n) поток продвинут на n байт."""
    data = QByteArray(b"\xaa\xbb\xcc\xdd\xee\xff")
    r = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    r.setVersion(QDataStream.Version.Qt_5_1)

    chunk1 = r.readRawData(3)
    chunk2 = r.readRawData(3)
    assert bytes(chunk1) == b"\xaa\xbb\xcc"
    assert bytes(chunk2) == b"\xdd\xee\xff"
    assert r.atEnd()


def test_readRawData_short_read_at_eof() -> None:
    """Запрос N байт когда осталось <N — статус становится ReadPastEnd."""
    data = QByteArray(b"\x01\x02\x03")
    r = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    r.setVersion(QDataStream.Version.Qt_5_1)
    _ = r.readRawData(10)  # запросили больше чем есть
    assert r.status() == QDataStream.Status.ReadPastEnd


# === writeRawData + readRawData roundtrip ===


def test_rawData_roundtrip() -> None:
    payload = b"\x00\xff\x80\x7f\x01\x02\x03\x04"
    data, s = _writer()
    s.writeRawData(payload)

    r = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    r.setVersion(QDataStream.Version.Qt_5_1)
    out = r.readRawData(len(payload))
    assert bytes(out) == payload


# === Mixed: writeRawData + writeUInt32 + readRawData + readUInt32 ===


def test_rawData_with_typed_writes_no_drift() -> None:
    """rawData не нарушает дальнейшие typed reads — нет невидимых размеров."""
    payload = b"raw-header"
    next_value = 0xDEADBEEF

    data, s = _writer()
    s.writeRawData(payload)
    s.writeUInt32(next_value)

    r = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    r.setVersion(QDataStream.Version.Qt_5_1)
    out_payload = r.readRawData(len(payload))
    out_value = r.readUInt32()

    assert bytes(out_payload) == payload
    assert out_value == next_value
    assert r.atEnd()


# === QDataStream(QByteArray) constructor shorthand ===


def test_QDataStream_constructor_from_qbytearray_implicit_readonly() -> None:
    """`QDataStream(serialized)` — implicit read-only mode (used in account.py:945).
    Phase 5 pure-Python implementation должна поддерживать этот shorthand."""
    payload = QByteArray(b"\x00\x00\x00\x00\xde\xad\xbe\xef")  # uint64 0xDEADBEEF
    stream = QDataStream(payload)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    value = stream.readUInt64()
    assert value == 0xDEADBEEF


def test_QDataStream_constructor_from_qbytearray_with_explicit_openmode() -> None:
    """Сравниваем shorthand vs explicit ReadOnly — должны дать тот же результат."""
    payload = QByteArray(b"\x01\x02\x03\x04")

    short = QDataStream(payload)
    short.setVersion(QDataStream.Version.Qt_5_1)

    explicit = QDataStream(payload, QIODevice.OpenModeFlag.ReadOnly)
    explicit.setVersion(QDataStream.Version.Qt_5_1)

    assert short.readUInt32() == explicit.readUInt32() == 0x01020304
