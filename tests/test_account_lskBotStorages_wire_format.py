"""lskBotStorages (0x1D) wire format — map: uint32 count + (FileKey, PeerId) pairs.

Источник истины: telegramdesktop/tdesktop dev branch, storage_account.cpp:
- enum line 104: `lskBotStorages = 0x1d, // data: PeerId botId`
- read line 493-503: `quint32 count; map.stream >> count; for i in range(count): map.stream >> FileKey key >> peerIdSerialized`
- write line 754-759: `mapData.stream << quint32(lskBotStorages) << quint32(_botStoragesMap.size()); for k,v in _botStoragesMap: mapData.stream << quint64(value) << SerializePeerId(key)`
- mapSize: `sizeof(quint32) * 2 + _botStoragesMap.size() * sizeof(quint64) * 2`
"""
import inspect

from opentele.td import account as account_module
from opentele.td.configs import FileKey, PeerId, lskType
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


def test_botStorages_roundtrip_via_qdatastream() -> None:
    """Stream-level: write uint32 count + N×(uint64 FileKey, uint64 PeerId), read обратно — пары совпадают."""
    test_pairs = [
        (FileKey(0xABCDEF0123456789), 1234567890),  # (key, peerIdSerialized)
        (FileKey(0xFEDCBA9876543210), 9876543210),
    ]
    data, stream = _write_stream()
    stream.writeUInt32(lskType.lskBotStorages)
    stream.writeUInt32(len(test_pairs))
    for key, peer_id in test_pairs:
        stream.writeUInt64(key)
        stream.writeUInt64(peer_id)

    reader = _read_stream(data)
    keyType = reader.readUInt32()
    count = reader.readUInt32()
    read_pairs = []
    for _ in range(count):
        k = reader.readUInt64()
        p = reader.readUInt64()
        read_pairs.append((k, p))

    assert keyType == lskType.lskBotStorages
    assert count == len(test_pairs)
    assert read_pairs == [(int(k), int(p)) for k, p in test_pairs]


def test_account_uses_map_not_single_uint64_for_botStorages() -> None:
    """Read-ветка должна использовать count + цикл, не один readUInt64()."""
    src = inspect.getsource(account_module)
    idx = src.find("lskType.lskBotStorages")
    assert idx >= 0
    snippet = src[idx : idx + 800]
    # Должен быть либо `for i in range(count)`, либо явный цикл с PeerId.FromSerialized
    assert "PeerId.FromSerialized" in snippet or "PeerId(" in snippet, (
        "lskBotStorages must deserialize PeerId, not read a single uint64"
    )
    assert "readUInt32()" in snippet, (
        "lskBotStorages must read uint32 count first"
    )


def test_account_botStoragesMap_is_dict_attribute() -> None:
    """В MapData должен быть атрибут botStoragesMap как dict, по аналогии с draftsMap."""
    src = inspect.getsource(account_module)
    assert "_botStoragesMap" in src, "MapData must have _botStoragesMap attribute"
    # Должен быть Dict[PeerId, FileKey] init и write-цикл с .items()
    assert "self._botStoragesMap" in src
