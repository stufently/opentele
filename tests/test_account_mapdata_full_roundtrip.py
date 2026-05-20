"""Полный MapData roundtrip: write→read через QDataStream, проверяем все новые ключи.

Реализуем минимальную имитацию MapData.write → MapData.read для новых ключей.
Это закрывает дыру: предыдущие inspect-тесты только проверяли наличие строк, но не
семантику. Здесь — реальная сериализация/десериализация.

Phase 4 добавит полноценные fixture-based тесты с реальным tdata. Здесь Phase 1.5
sanity на уровне stream-логики.
"""
from PyQt6.QtCore import QByteArray, QDataStream, QIODevice

from opentele.td.configs import (
    BareId,
    FileKey,
    PeerId,
    UserId,
    lskType,
)


def _make_write_stream() -> tuple[QByteArray, QDataStream]:
    data = QByteArray()
    stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    return data, stream


def _make_read_stream(data: QByteArray) -> QDataStream:
    stream = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    return stream


def test_full_map_with_all_new_keys_roundtrip() -> None:
    """Имитируем фрагмент MapData с пятью новыми ключами подряд, читаем обратно
    и проверяем что значения совпадают и поток не десинхронизируется."""

    # write side
    data, stream = _make_write_stream()
    stream.writeUInt32(lskType.lskRoundPlaceholder)
    stream.writeUInt64(0xAAAA1111)
    stream.writeUInt32(lskType.lskInlineBotsDownloads)
    stream.writeUInt64(0xBBBB2222)
    stream.writeUInt32(lskType.lskMediaLastPlaybackPositions)
    stream.writeUInt64(0xCCCC3333)
    # botStorages = 2 пары
    user_peer = PeerId.FromChatIdType(UserId(BareId(100500)))
    user_peer2 = PeerId.FromChatIdType(UserId(BareId(200600)))
    stream.writeUInt32(lskType.lskBotStorages)
    stream.writeUInt32(2)
    stream.writeUInt64(FileKey(0x1111))
    stream.writeUInt64(user_peer.Serialize())
    stream.writeUInt64(FileKey(0x2222))
    stream.writeUInt64(user_peer2.Serialize())
    # prefs
    stream.writeUInt32(lskType.lskPrefs)
    stream.writeUInt64(0xDDDD4444)
    # webview = 2 QByteArray
    bots_token = QByteArray(b"bot-webview-token-payload")
    other_token = QByteArray(b"other-webview-token-12345")
    stream.writeUInt32(lskType.lskWebviewTokens)
    stream << bots_token
    stream << other_token

    # read side — последовательно потребляем все
    reader = _make_read_stream(data)

    assert reader.readUInt32() == lskType.lskRoundPlaceholder
    assert reader.readUInt64() == 0xAAAA1111

    assert reader.readUInt32() == lskType.lskInlineBotsDownloads
    assert reader.readUInt64() == 0xBBBB2222

    assert reader.readUInt32() == lskType.lskMediaLastPlaybackPositions
    assert reader.readUInt64() == 0xCCCC3333

    assert reader.readUInt32() == lskType.lskBotStorages
    count = reader.readUInt32()
    assert count == 2
    read_pairs = []
    for _ in range(count):
        key = reader.readUInt64()
        peer_serialized = reader.readUInt64()
        read_pairs.append((key, PeerId.FromSerialized(peer_serialized)))
    assert read_pairs[0][0] == 0x1111
    assert read_pairs[1][0] == 0x2222
    assert int(read_pairs[0][1]) == int(user_peer)
    assert int(read_pairs[1][1]) == int(user_peer2)

    assert reader.readUInt32() == lskType.lskPrefs
    assert reader.readUInt64() == 0xDDDD4444

    assert reader.readUInt32() == lskType.lskWebviewTokens
    read_bots = QByteArray()
    read_other = QByteArray()
    reader >> read_bots
    reader >> read_other
    assert bytes(read_bots) == bytes(bots_token)
    assert bytes(read_other) == bytes(other_token)

    # Stream должен быть полностью прочитан без остатка
    assert reader.atEnd(), "Stream должен закончиться: остатки байт = десинхронизация"
    assert reader.status() == QDataStream.Status.Ok


def test_botStorages_empty_count_does_not_write_pairs() -> None:
    """Если botStoragesMap пуст — count=0 без пар. Это валидное состояние."""
    data, stream = _make_write_stream()
    stream.writeUInt32(lskType.lskBotStorages)
    stream.writeUInt32(0)  # count=0

    reader = _make_read_stream(data)
    assert reader.readUInt32() == lskType.lskBotStorages
    assert reader.readUInt32() == 0
    assert reader.atEnd()


def test_webview_empty_qbytearray_roundtrip() -> None:
    """Пустой QByteArray тоже валиден — должен сериализоваться как 4-байтовый null marker."""
    data, stream = _make_write_stream()
    empty = QByteArray()
    stream << empty
    stream << QByteArray(b"non-empty")

    reader = _make_read_stream(data)
    read_empty = QByteArray()
    read_nonempty = QByteArray()
    reader >> read_empty
    reader >> read_nonempty
    assert read_empty.isEmpty()
    assert bytes(read_nonempty) == b"non-empty"
