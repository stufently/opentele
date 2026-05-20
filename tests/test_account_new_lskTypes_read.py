"""Read-логика новых lskType: stream-level sanity + структурная проверка кода.

Полный roundtrip через MapData делается в Phase 4 (с фикстурами реального tdata).
Здесь — минимально: проверяем stream primitives и наличие elif веток в исходнике.
"""
import inspect

from opentele.td import account as account_module
from opentele.td.configs import lskType
from PyQt6.QtCore import QByteArray, QDataStream, QIODevice


def _stream_writer() -> tuple[QByteArray, QDataStream]:
    data = QByteArray()
    stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    return data, stream


def _stream_reader(data: QByteArray) -> QDataStream:
    stream = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
    stream.setVersion(QDataStream.Version.Qt_5_1)
    return stream


def test_qdatastream_roundtrip_lskRoundPlaceholder() -> None:
    """Stream-level: пишем uint32+uint64, читаем обратно тот же uint64."""
    expected = 0xCAFEBABEDEADBEEF
    data, stream = _stream_writer()
    stream.writeUInt32(lskType.lskRoundPlaceholder)
    stream.writeUInt64(expected)

    reader = _stream_reader(data)
    keyType = reader.readUInt32()
    value = reader.readUInt64()
    assert keyType == lskType.lskRoundPlaceholder
    assert value == expected


def test_account_module_has_read_branch_for_all_new_lskTypes() -> None:
    """В исходнике account.py должны быть elif ветки для каждого нового ключа."""
    src = inspect.getsource(account_module)
    for name in (
        "lskRoundPlaceholder",
        "lskInlineBotsDownloads",
        "lskMediaLastPlaybackPositions",
        "lskBotStorages",
    ):
        assert f"lskType.{name}" in src, (
            f"account.py не содержит ветку чтения для {name}"
        )


def test_lskWebviewTokens_does_not_break_loop() -> None:
    """RobertAzovski conflict artifact: ветка lskWebviewTokens не должна ставить
    is_finished = True (это обрывало чтение последующих ключей).
    Также не должна быть пустой — должно быть чтение QByteArray (по TDesktop format)."""
    src = inspect.getsource(account_module)
    idx = src.find("lskType.lskWebviewTokens")
    assert idx >= 0
    snippet = src[idx : idx + 500]
    # is_finished = True больше не должно быть в этой ветке (был conflict-artifact).
    assert "is_finished = True" not in snippet.split("elif")[0], (
        "lskWebviewTokens branch must not set is_finished — that broke read loop"
    )
    # Должно быть чтение QByteArray (>> operator). Wire format уточнён в Phase 1.5
    # после ревью трёх AI и сверки с TDesktop storage_account.cpp.
    assert ">> webviewStorageToken" in snippet, (
        "lskWebviewTokens branch must read two QByteArray (bots, other) via stream >>"
    )
