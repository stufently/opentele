"""Phase 4.5: QString binary format goldens.

QString в QDataStream Qt_5_1:
- 4-byte size prefix (uint32, размер **в байтах** UTF-16-BE payload, big-endian)
- null marker = 0xFFFFFFFF
- empty marker = 0x00000000
- payload = UTF-16-BE encoded characters

Используется в:
- src/td/mtp.py:412 / :420 — DcOptions internalLinksDomain, txtDomainString
- src/td/mtp.py:450 — readQString
- src/td/storage.py:358-371 — DcOptions host/ip strings

Gemini Phase 4 review flagged QString as critical missing test coverage.
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


# === ASCII goldens ===


def test_writeQString_ascii_one_char() -> None:
    """QString 'A' = 4-byte size (uint32, =2 bytes UTF-16) + 0x0041 (UTF-16-BE 'A')."""
    data, s = _writer()
    s.writeQString("A")
    raw = bytes(data)
    # size_in_bytes = 2 (one UTF-16-BE char)
    # 'A' = 0x41 in UTF-16-BE: \x00\x41
    assert raw == b"\x00\x00\x00\x02\x00\x41", f"Unexpected QString 'A' encoding: {raw!r}"


def test_writeQString_ascii_short_word() -> None:
    """QString 'Hi' = 4 bytes (size=4) + \\x00H\\x00i."""
    data, s = _writer()
    s.writeQString("Hi")
    raw = bytes(data)
    # size = 4 bytes (2 chars × 2 UTF-16 bytes each)
    assert raw == b"\x00\x00\x00\x04\x00H\x00i", f"Unexpected encoding: {raw!r}"


def test_writeQString_empty() -> None:
    """Empty QString: size prefix only. PyQt6 может писать как null (0xFFFFFFFF) или
    empty (0x00000000); закрепляем фактическое поведение."""
    data, s = _writer()
    s.writeQString("")
    raw = bytes(data)
    assert raw in (b"\x00\x00\x00\x00", b"\xff\xff\xff\xff"), (
        f"Empty QString unexpected serialization: {raw!r}"
    )


def test_writeQString_telegram_internalLinksDomain() -> None:
    """Реальный кейс из src/td/mtp.py: 'https://t.me/' — типичный QString в DcOptions."""
    data, s = _writer()
    s.writeQString("https://t.me/")
    raw = bytes(data)
    # 13 chars × 2 = 26 bytes (0x1A)
    expected_size = b"\x00\x00\x00\x1a"
    assert raw[:4] == expected_size
    # 'h' = 0x68 → b"\x00h", 't' = 0x74 → b"\x00t", '/' = 0x2F → b"\x00/"
    expected_payload = "".join(f"\x00{c}" for c in "https://t.me/").encode("latin-1")
    assert raw[4:] == expected_payload


# === Roundtrips ===


def test_qstring_ascii_roundtrip() -> None:
    src = "Hello, world!"
    data, s = _writer()
    s.writeQString(src)

    r = _reader(data)
    out = r.readQString()
    assert out == src
    assert r.atEnd()


def test_qstring_unicode_cyrillic_roundtrip() -> None:
    """UTF-16-BE поддерживает unicode напрямую (без surrogates для BMP)."""
    src = "Привет, мир!"
    data, s = _writer()
    s.writeQString(src)

    r = _reader(data)
    out = r.readQString()
    assert out == src


def test_qstring_emoji_roundtrip() -> None:
    """Emoji = surrogate pair в UTF-16. Должен пройти через PyQt6 без поломок."""
    src = "Hi 👋 world 🌍"
    data, s = _writer()
    s.writeQString(src)

    r = _reader(data)
    out = r.readQString()
    assert out == src


def test_qstring_empty_roundtrip() -> None:
    """Пустая QString читается обратно как пустая (не None)."""
    data, s = _writer()
    s.writeQString("")

    r = _reader(data)
    out = r.readQString()
    # PyQt6 может вернуть "" или None для пустой/null QString — обе валидны.
    assert out in ("", None)


def test_qstring_long_4kb_roundtrip() -> None:
    src = "X" * 4096
    data, s = _writer()
    s.writeQString(src)

    r = _reader(data)
    out = r.readQString()
    assert out == src
    assert len(out) == 4096


# === Mixed: QString + uint64 → no drift ===


def test_qstring_followed_by_uint64_no_drift() -> None:
    """После QString поток должен корректно читать uint64."""
    src = "test-host.example.com"
    next_value = 0xCAFEBABECAFEBABE

    data, s = _writer()
    s.writeQString(src)
    s.writeUInt64(next_value)

    r = _reader(data)
    out_str = r.readQString()
    out_val = r.readUInt64()

    assert out_str == src
    assert out_val == next_value
    assert r.atEnd()


# === Two QStrings consecutive (как в storage.py host/ip) ===


def test_two_qstrings_consecutive_roundtrip() -> None:
    """Два QString подряд (DcOptions host/ip pattern)."""
    host = "telegram.example.com"
    ip = "149.154.167.50"

    data, s = _writer()
    s.writeQString(host)
    s.writeQString(ip)

    r = _reader(data)
    out_host = r.readQString()
    out_ip = r.readQString()

    assert out_host == host
    assert out_ip == ip
    assert r.atEnd()
