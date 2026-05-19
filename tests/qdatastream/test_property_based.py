"""Phase 4: property-based fuzzing для QDataStream через hypothesis.

Эти тесты — самый сильный safety net для Phase 5 pure-Python rewrite.
Hypothesis генерирует тысячи случайных входов; pure-Python реализация должна
давать byte-identical output для каждого.
"""
from hypothesis import given, settings
from hypothesis import strategies as st
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


# === UInt64 list roundtrip ===


@given(values=st.lists(st.integers(min_value=0, max_value=2**64 - 1), max_size=50))
@settings(max_examples=200, deadline=2000)
def test_uint64_list_roundtrip(values) -> None:
    """Любая последовательность uint64 read-back-able через QDataStream."""
    data, s = _writer()
    for v in values:
        s.writeUInt64(v)

    r = _reader(data)
    out = [r.readUInt64() for _ in values]

    assert out == values
    assert r.atEnd()


# === Int32 list roundtrip (включая negatives) ===


@given(values=st.lists(st.integers(min_value=-(2**31), max_value=2**31 - 1), max_size=50))
@settings(max_examples=200, deadline=2000)
def test_int32_list_roundtrip(values) -> None:
    data, s = _writer()
    for v in values:
        s.writeInt32(v)

    r = _reader(data)
    out = [r.readInt32() for _ in values]
    assert out == values
    assert r.atEnd()


# === Mixed types ===


@given(
    u32=st.integers(min_value=0, max_value=2**32 - 1),
    u64=st.integers(min_value=0, max_value=2**64 - 1),
    i32=st.integers(min_value=-(2**31), max_value=2**31 - 1),
)
@settings(max_examples=100, deadline=1000)
def test_mixed_types_roundtrip(u32, u64, i32) -> None:
    """uint32 + uint64 + int32 sequence не вызывает drift."""
    data, s = _writer()
    s.writeUInt32(u32)
    s.writeUInt64(u64)
    s.writeInt32(i32)

    r = _reader(data)
    assert r.readUInt32() == u32
    assert r.readUInt64() == u64
    assert r.readInt32() == i32
    assert r.atEnd()


# === QByteArray roundtrip ===


@given(payload=st.binary(min_size=1, max_size=4096))
@settings(max_examples=100, deadline=2000)
def test_qbytearray_roundtrip(payload) -> None:
    """Любой непустой bytes payload сохраняется через QByteArray."""
    src = QByteArray(payload)
    data, s = _writer()
    s << src

    r = _reader(data)
    out = QByteArray()
    r >> out

    assert bytes(out) == payload
    assert r.atEnd()


@given(
    payloads=st.lists(
        st.binary(min_size=0, max_size=512),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=100, deadline=3000)
def test_qbytearray_list_roundtrip(payloads) -> None:
    """Серия QByteArray подряд читается в правильном порядке."""
    data, s = _writer()
    for p in payloads:
        s << QByteArray(p)

    r = _reader(data)
    out = []
    for _ in payloads:
        qba = QByteArray()
        r >> qba
        out.append(bytes(qba))

    # NB: empty QByteArray() vs QByteArray(b"") могут давать null marker;
    # bytes() обоих = b"". Сравниваем по bytes.
    assert out == [bytes(p) for p in payloads]
    assert r.atEnd()


# === Byte-identity invariants ===


@given(
    value=st.integers(min_value=0, max_value=2**64 - 1),
)
@settings(max_examples=100, deadline=500)
def test_uint64_byte_layout_is_8_bytes(value) -> None:
    """uint64 always writes exactly 8 bytes."""
    data, s = _writer()
    s.writeUInt64(value)
    assert len(bytes(data)) == 8


@given(value=st.integers(min_value=0, max_value=2**32 - 1))
@settings(max_examples=100, deadline=500)
def test_uint32_byte_layout_is_4_bytes(value) -> None:
    data, s = _writer()
    s.writeUInt32(value)
    assert len(bytes(data)) == 4


# === Stream concatenation ===


@given(
    a=st.integers(min_value=0, max_value=2**64 - 1),
    b=st.integers(min_value=0, max_value=2**64 - 1),
)
@settings(max_examples=100, deadline=500)
def test_two_uint64_writes_concatenate(a, b) -> None:
    """Two writes produce 16 bytes total — pure concatenation, no framing."""
    data, s = _writer()
    s.writeUInt64(a)
    s.writeUInt64(b)
    raw = bytes(data)
    assert len(raw) == 16
    assert raw[:8] == a.to_bytes(8, "big")
    assert raw[8:] == b.to_bytes(8, "big")
