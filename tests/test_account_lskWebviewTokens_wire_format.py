"""lskWebviewTokens (0x19) wire format — два QByteArray, не два uint64.

Источник истины: telegramdesktop/tdesktop dev branch, storage_account.cpp:
- enum line 100: `lskWebviewTokens = 0x19, // data: QByteArray bots, QByteArray other`
- read line 488: `map.stream >> webviewStorageTokenBots >> webviewStorageTokenOther`
- write line 737: `mapData.stream << _webviewStorageIdBots.token << _webviewStorageIdOther.token`

В Phase 1 (init commit `1f6a1cd`) реализовали как два uint64 — это ошибка.
"""
from opentele.td.configs import lskType
from PyQt6.QtCore import QByteArray, QDataStream, QIODevice


def _read_stream(data: QByteArray) -> QDataStream:
    stream = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    return stream


def _write_stream() -> tuple[QByteArray, QDataStream]:
    data = QByteArray()
    stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    return data, stream


def test_webview_tokens_roundtrip_through_qdatastream() -> None:
    """Stream-level: пишем 2 QByteArray, читаем обратно — байты совпадают."""
    bots_token = QByteArray(b"bot-token-payload-\x00\x01\x02\xff")
    other_token = QByteArray(b"other-very-different-payload")

    data, stream = _write_stream()
    stream.writeUInt32(lskType.lskWebviewTokens)
    stream << bots_token
    stream << other_token

    reader = _read_stream(data)
    keyType = reader.readUInt32()
    read_bots = QByteArray()
    read_other = QByteArray()
    reader >> read_bots
    reader >> read_other

    assert keyType == lskType.lskWebviewTokens
    assert bytes(read_bots) == bytes(bots_token)
    assert bytes(read_other) == bytes(other_token)


def test_webview_tokens_qbytearray_size_differs_from_two_uint64() -> None:
    """QByteArray serialization включает 4-байтовый префикс длины,
    значит размер записи != 16 байт (как у двух uint64). Если payload
    короткий — больше 16; если пустой — 4+4=8."""
    bots_token = QByteArray(b"X" * 32)
    other_token = QByteArray(b"")

    data, stream = _write_stream()
    stream << bots_token
    stream << other_token

    # bots: 4 (length prefix) + 32 (payload) = 36
    # other: 4 (length prefix for empty/-1 marker) = 4
    # total: 40 (а не 16 как было бы у двух uint64)
    raw = bytes(data)
    assert len(raw) > 16, (
        f"two QByteArray serialization must produce > 16 bytes for non-empty payload, "
        f"got {len(raw)}; if 16 — реализация всё ещё пишет два uint64"
    )


def test_account_read_uses_qbytearray_for_webview() -> None:
    """Inspect-guard: read-ветка lskWebviewTokens должна работать с QByteArray,
    а не с readUInt64."""
    import inspect

    from opentele.td import account as account_module

    src = inspect.getsource(account_module)
    # Найти ветку lskWebviewTokens
    idx = src.find("lskType.lskWebviewTokens")
    assert idx >= 0
    # До следующего elif/else или closing
    end = idx + 500
    snippet = src[idx:end]
    # Должен быть либо `>> webviewStorageTokenBots` (QByteArray стиль) либо `readBytes`.
    assert ">> webviewStorageToken" in snippet or "readBytes" in snippet, (
        "lskWebviewTokens read branch must use QByteArray semantics (>>), not readUInt64"
    )
    assert "readUInt64()" not in snippet, (
        "lskWebviewTokens read branch must not call readUInt64() — it's two QByteArray"
    )
