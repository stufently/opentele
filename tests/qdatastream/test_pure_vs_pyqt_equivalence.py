"""Phase 5 (Codex review fix): byte-identity между PyQt6 и pure-Python.

Phase 4 goldens проверяют PyQt6 как oracle. Этот файл — отдельная **direct
comparison** между PyQt6 и нашим opentele.td.qdatastream — для каждого primitive
сериализация даёт **byte-identical** output.

Это финальный safety net Phase 5: если pure-Python отклоняется от PyQt6 в
любом байте, этот тест fails.
"""
from PyQt6.QtCore import QByteArray as QtQByteArray
from PyQt6.QtCore import QDataStream as QtQDataStream
from PyQt6.QtCore import QIODevice as QtQIODevice

from opentele.td.qdatastream import QByteArray as PureQByteArray
from opentele.td.qdatastream import QDataStream as PureQDataStream
from opentele.td.qdatastream import QIODevice as PureQIODevice


def _qt_writer():
    """PyQt6 writer."""
    data = QtQByteArray()
    s = QtQDataStream(data, QtQIODevice.OpenModeFlag.WriteOnly)
    s.setVersion(QtQDataStream.Version.Qt_5_1)
    return data, s


def _pure_writer():
    """Pure-Python writer."""
    data = PureQByteArray()
    s = PureQDataStream(data, PureQIODevice.OpenModeFlag.WriteOnly)
    s.setVersion(PureQDataStream.Version.Qt_5_1)
    return data, s


# === UInt8/16/32/64 ===


def test_writeUInt8_byte_identical() -> None:
    for v in [0, 1, 0x7F, 0x80, 0xFE, 0xFF]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeUInt8(v)

        pure_data, pure_s = _pure_writer()
        pure_s.writeUInt8(v)

        assert bytes(qt_data) == bytes(pure_data), (
            f"UInt8 {v}: Qt={bytes(qt_data)!r} vs Pure={bytes(pure_data)!r}"
        )


def test_writeUInt16_byte_identical() -> None:
    for v in [0, 1, 0x7FFF, 0x8000, 0xFFFE, 0xFFFF]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeUInt16(v)

        pure_data, pure_s = _pure_writer()
        pure_s.writeUInt16(v)

        assert bytes(qt_data) == bytes(pure_data), f"UInt16 {v}: mismatch"


def test_writeUInt32_byte_identical() -> None:
    for v in [0, 1, 0xCAFEBABE, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeUInt32(v)

        pure_data, pure_s = _pure_writer()
        pure_s.writeUInt32(v)

        assert bytes(qt_data) == bytes(pure_data), f"UInt32 0x{v:X}: mismatch"


def test_writeUInt64_byte_identical() -> None:
    for v in [0, 1, 0xDEADBEEFCAFEBABE, 0x7FFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeUInt64(v)

        pure_data, pure_s = _pure_writer()
        pure_s.writeUInt64(v)

        assert bytes(qt_data) == bytes(pure_data), f"UInt64 0x{v:X}: mismatch"


# === Int32/Int64 (two's complement) ===


def test_writeInt32_negative_byte_identical() -> None:
    for v in [-(2**31), -1, 0, 1, 2**31 - 1]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeInt32(v)

        pure_data, pure_s = _pure_writer()
        pure_s.writeInt32(v)

        assert bytes(qt_data) == bytes(pure_data), f"Int32 {v}: mismatch"


def test_writeInt64_negative_byte_identical() -> None:
    for v in [-(2**63), -1, 0, 1, 2**63 - 1]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeInt64(v)

        pure_data, pure_s = _pure_writer()
        pure_s.writeInt64(v)

        assert bytes(qt_data) == bytes(pure_data), f"Int64 {v}: mismatch"


# === QByteArray serialization (size prefix + payload) ===


def test_writeQByteArray_null_byte_identical() -> None:
    """QByteArray() (null) → 0xFFFFFFFF in both."""
    qt_data, qt_s = _qt_writer()
    qt_s << QtQByteArray()

    pure_data, pure_s = _pure_writer()
    pure_s << PureQByteArray()

    assert bytes(qt_data) == bytes(pure_data), (
        f"Null QByteArray: Qt={bytes(qt_data)!r} vs Pure={bytes(pure_data)!r}"
    )


def test_writeQByteArray_empty_byte_identical() -> None:
    """QByteArray(b'') (empty) — ожидаем те же байты в обоих."""
    qt_data, qt_s = _qt_writer()
    qt_s << QtQByteArray(b"")

    pure_data, pure_s = _pure_writer()
    pure_s << PureQByteArray(b"")

    assert bytes(qt_data) == bytes(pure_data), (
        f"Empty QByteArray: Qt={bytes(qt_data)!r} vs Pure={bytes(pure_data)!r}"
    )


def test_writeQByteArray_short_byte_identical() -> None:
    """Short payload."""
    payload = b"hello world"
    qt_data, qt_s = _qt_writer()
    qt_s << QtQByteArray(payload)

    pure_data, pure_s = _pure_writer()
    pure_s << PureQByteArray(payload)

    assert bytes(qt_data) == bytes(pure_data)


def test_writeQByteArray_binary_byte_identical() -> None:
    """Binary payload with null bytes / high bytes."""
    payload = bytes(range(256))  # 0x00..0xFF
    qt_data, qt_s = _qt_writer()
    qt_s << QtQByteArray(payload)

    pure_data, pure_s = _pure_writer()
    pure_s << PureQByteArray(payload)

    assert bytes(qt_data) == bytes(pure_data)


def test_writeQByteArray_large_4kb_byte_identical() -> None:
    payload = b"\xAB" * 4096
    qt_data, qt_s = _qt_writer()
    qt_s << QtQByteArray(payload)

    pure_data, pure_s = _pure_writer()
    pure_s << PureQByteArray(payload)

    assert bytes(qt_data) == bytes(pure_data)


# === QString ===


def test_writeQString_ascii_byte_identical() -> None:
    for s in ["A", "Hello", "https://t.me/", ""]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeQString(s)

        pure_data, pure_s = _pure_writer()
        pure_s.writeQString(s)

        assert bytes(qt_data) == bytes(pure_data), (
            f"QString {s!r}: Qt={bytes(qt_data)!r} vs Pure={bytes(pure_data)!r}"
        )


def test_writeQString_unicode_byte_identical() -> None:
    for s in ["Привет", "你好", "🌍", "mixed: Hi 👋 мир"]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeQString(s)

        pure_data, pure_s = _pure_writer()
        pure_s.writeQString(s)

        assert bytes(qt_data) == bytes(pure_data), f"QString unicode {s!r}: mismatch"


# === RawData ===


def test_writeRawData_byte_identical() -> None:
    for payload in [b"", b"a", b"hello", bytes(range(256)), b"X" * 1024]:
        qt_data, qt_s = _qt_writer()
        qt_s.writeRawData(payload)

        pure_data, pure_s = _pure_writer()
        pure_s.writeRawData(payload)

        assert bytes(qt_data) == bytes(pure_data), (
            f"RawData {len(payload)}b: Qt={bytes(qt_data)!r} vs Pure={bytes(pure_data)!r}"
        )


# === Mixed sequence — typical MapData-like writes ===


def test_mixed_writes_byte_identical() -> None:
    """Сложная последовательность: uint32 + uint64 + QByteArray + QString.
    Имитирует фрагмент MapData."""
    qt_data, qt_s = _qt_writer()
    qt_s.writeUInt32(0xCAFEBABE)
    qt_s.writeUInt64(0xDEADBEEFCAFEBABE)
    qt_s << QtQByteArray(b"webview-token-bots")
    qt_s.writeQString("https://t.me/")
    qt_s.writeInt32(-42)

    pure_data, pure_s = _pure_writer()
    pure_s.writeUInt32(0xCAFEBABE)
    pure_s.writeUInt64(0xDEADBEEFCAFEBABE)
    pure_s << PureQByteArray(b"webview-token-bots")
    pure_s.writeQString("https://t.me/")
    pure_s.writeInt32(-42)

    assert bytes(qt_data) == bytes(pure_data), (
        f"Mixed sequence diverged:\n  Qt:   {bytes(qt_data).hex()}\n  Pure: {bytes(pure_data).hex()}"
    )


# === Cross-reads: PyQt6 writes → pure-Python reads (and vice versa) ===


def test_pure_can_read_pyqt_output() -> None:
    """Что pure-Python пишет PyQt6, то же и читается обратно через PyQt6."""
    qt_data, qt_s = _qt_writer()
    qt_s.writeUInt32(0x12345678)
    qt_s.writeUInt64(0xCAFEBABE)
    qt_s << QtQByteArray(b"payload")
    qt_s.writeQString("Hello, мир")

    # Now read with pure-Python
    raw = bytes(qt_data)
    pure_data = PureQByteArray(raw)
    pure_r = PureQDataStream(pure_data, PureQIODevice.OpenModeFlag.ReadOnly)
    pure_r.setVersion(PureQDataStream.Version.Qt_5_1)

    assert pure_r.readUInt32() == 0x12345678
    assert pure_r.readUInt64() == 0xCAFEBABE
    qba = PureQByteArray()
    pure_r >> qba
    assert bytes(qba) == b"payload"
    assert pure_r.readQString() == "Hello, мир"


def test_pyqt_can_read_pure_output() -> None:
    """Что pure-Python пишет, то PyQt6 правильно читает обратно."""
    pure_data, pure_s = _pure_writer()
    pure_s.writeUInt32(0x12345678)
    pure_s.writeUInt64(0xCAFEBABE)
    pure_s << PureQByteArray(b"payload")
    pure_s.writeQString("Hello, мир")

    # Read with PyQt6
    raw = bytes(pure_data)
    qt_data_in = QtQByteArray(raw)
    qt_r = QtQDataStream(qt_data_in, QtQIODevice.OpenModeFlag.ReadOnly)
    qt_r.setVersion(QtQDataStream.Version.Qt_5_1)

    assert qt_r.readUInt32() == 0x12345678
    assert qt_r.readUInt64() == 0xCAFEBABE
    qba = QtQByteArray()
    qt_r >> qba
    assert bytes(qba) == b"payload"
    assert qt_r.readQString() == "Hello, мир"
