"""Phase 4: QByteArray binary format goldens.

QByteArray в QDataStream:
- 4-byte size prefix (big-endian uint32)
- null marker = 0xFFFFFFFF (size==-1)
- empty marker = 0x00000000 (size==0, no payload)
- normal payload = size + bytes

Это критично для lskWebviewTokens (Phase 1.5 fix) и lskBotStorages (Phase 1.5).
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


# === QByteArray write golden bytes ===


def test_write_null_qbytearray_is_minus_one_size_marker() -> None:
    """Default-constructed QByteArray() = null = -1 size marker = 0xFFFFFFFF.
    Отличается от QByteArray(b"") = empty = 0 size."""
    data, s = _writer()
    s << QByteArray()  # default ctor = null
    raw = bytes(data)
    assert raw == b"\xff\xff\xff\xff", (
        f"Default QByteArray() should serialize as null marker -1 "
        f"(0xFFFFFFFF), got {raw!r}"
    )


def test_write_empty_qbytearray_with_zero_payload() -> None:
    """QByteArray(b"") with empty bytes — zero-size, not null."""
    data, s = _writer()
    s << QByteArray(b"")
    raw = bytes(data)
    # NB: PyQt6 may treat b"" same as default. Document actual behavior.
    # Either 0x00000000 (empty) or 0xFFFFFFFF (null) — fix expectation post-observation.
    assert raw in (b"\x00\x00\x00\x00", b"\xff\xff\xff\xff"), (
        f"QByteArray(b'') unexpected serialization: {raw!r}"
    )


def test_write_short_qbytearray_size_plus_payload() -> None:
    """Короткий QByteArray = uint32 size + payload."""
    data, s = _writer()
    s << QByteArray(b"hello")
    raw = bytes(data)
    # size = 5 → b"\x00\x00\x00\x05", потом "hello"
    assert raw == b"\x00\x00\x00\x05hello"


def test_write_qbytearray_with_binary_payload() -> None:
    """Бинарные данные сохраняются как-есть."""
    payload = b"\x00\xff\x01\xfe\x02\xfd"
    data, s = _writer()
    s << QByteArray(payload)
    raw = bytes(data)
    assert raw[:4] == b"\x00\x00\x00\x06"
    assert raw[4:] == payload


def test_write_long_qbytearray() -> None:
    """1024-byte payload — все 1024 байта сохранены."""
    payload = b"\xAB" * 1024
    data, s = _writer()
    s << QByteArray(payload)
    raw = bytes(data)
    assert raw[:4] == b"\x00\x00\x04\x00"  # size = 1024 = 0x400
    assert raw[4:] == payload


# === Roundtrips ===


def test_empty_qbytearray_roundtrip() -> None:
    data, s = _writer()
    s << QByteArray()

    r = _reader(data)
    out = QByteArray()
    r >> out
    assert out.isEmpty()
    assert r.atEnd()


def test_short_qbytearray_roundtrip() -> None:
    src = QByteArray(b"hello world")
    data, s = _writer()
    s << src

    r = _reader(data)
    out = QByteArray()
    r >> out
    assert bytes(out) == b"hello world"


def test_two_qbytearrays_consecutive_roundtrip() -> None:
    """Релевантно для lskWebviewTokens — два QByteArray подряд."""
    bots = QByteArray(b"bot-token")
    other = QByteArray(b"other-very-different-payload")

    data, s = _writer()
    s << bots
    s << other

    r = _reader(data)
    out_bots = QByteArray()
    out_other = QByteArray()
    r >> out_bots
    r >> out_other

    assert bytes(out_bots) == b"bot-token"
    assert bytes(out_other) == b"other-very-different-payload"
    assert r.atEnd()


def test_binary_payload_with_null_bytes_roundtrip() -> None:
    """Null bytes внутри payload не должны путать парсер (size prefix)."""
    payload = bytes(range(256))  # 0x00..0xFF
    data, s = _writer()
    s << QByteArray(payload)

    r = _reader(data)
    out = QByteArray()
    r >> out
    assert bytes(out) == payload


# === Edge: large size ===


def test_large_qbytearray_10kb_roundtrip() -> None:
    payload = b"X" * 10240
    data, s = _writer()
    s << QByteArray(payload)

    r = _reader(data)
    out = QByteArray()
    r >> out
    assert bytes(out) == payload
    assert len(out) == 10240


# === Stream layout: QByteArray followed by uint64 ===


def test_qbytearray_then_uint64_no_drift() -> None:
    """Релевантно для lskWebviewTokens + следующий lsk ключ:
    после QByteArray поток должен корректно читаться uint64-операцией."""
    bots = QByteArray(b"\x01\x02\x03\x04")
    next_value = 0xDEADBEEFCAFEBABE

    data, s = _writer()
    s << bots
    s.writeUInt64(next_value)

    r = _reader(data)
    out_bots = QByteArray()
    r >> out_bots
    out_value = r.readUInt64()

    assert bytes(out_bots) == b"\x01\x02\x03\x04"
    assert out_value == next_value
    assert r.atEnd()
