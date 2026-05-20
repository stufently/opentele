"""lskPrefs (0x1E) wire format — uint64 prefsKey.

Источник истины: telegramdesktop/tdesktop dev branch, storage_account.cpp:
- enum line 105: `lskPrefs = 0x1e, // no data`
- read line 411: `map.stream >> prefsKey`
- write line 687: `mapData.stream << quint32(lskPrefs) << quint64(_prefsKey)`
- mapSize: `sizeof(quint32) + sizeof(quint64)` (12 bytes)

Этот ключ упустили в Phase 1 init. Без него tdata с prefs секцией silently
десинхронизируется через `else: logging.warning(...)`.
"""
import inspect

from PyQt6.QtCore import QByteArray, QDataStream, QIODevice

from opentele.td import account as account_module
from opentele.td.configs import lskType


def _read_stream(data: QByteArray) -> QDataStream:
    stream = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    return stream


def _write_stream() -> tuple[QByteArray, QDataStream]:
    data = QByteArray()
    stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    return data, stream


def test_lskPrefs_constant() -> None:
    """Константа lskPrefs должна быть 0x1E."""
    assert lskType.lskPrefs == 0x1E


def test_lskPrefs_roundtrip_via_qdatastream() -> None:
    """Stream-level: write uint32 type + uint64 prefsKey, read обратно."""
    expected = 0xDEADBEEF12345678
    data, stream = _write_stream()
    stream.writeUInt32(lskType.lskPrefs)
    stream.writeUInt64(expected)

    reader = _read_stream(data)
    keyType = reader.readUInt32()
    value = reader.readUInt64()
    assert keyType == lskType.lskPrefs
    assert value == expected


def test_account_module_has_lskPrefs_read_branch() -> None:
    """В account.py должна быть elif ветка для lskPrefs."""
    src = inspect.getsource(account_module)
    assert "lskType.lskPrefs" in src, (
        "account.py не содержит ветку чтения для lskPrefs"
    )


def test_account_module_has_lskPrefs_write() -> None:
    """В account.py должен быть writeUInt32(lskType.lskPrefs)."""
    src = inspect.getsource(account_module)
    assert "writeUInt32(lskType.lskPrefs)" in src, (
        "account.py не пишет lskPrefs в map"
    )
