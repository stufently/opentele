"""Новые lskType ключи для Telegram Desktop 5.x-6.x (RobertAzovski).

Без этих ключей opentele silently игнорирует часть данных свежих tdata или
бьётся об ExpectStreamStatus.
"""
from opentele.td.configs import lskType


def test_lskRoundPlaceholder_constant() -> None:
    assert lskType.lskRoundPlaceholder == 0x1A


def test_lskInlineBotsDownloads_constant() -> None:
    assert lskType.lskInlineBotsDownloads == 0x1B


def test_lskMediaLastPlaybackPositions_constant() -> None:
    assert lskType.lskMediaLastPlaybackPositions == 0x1C


def test_lskBotStorages_constant() -> None:
    assert lskType.lskBotStorages == 0x1D


def test_existing_lskWebviewTokens_still_correct() -> None:
    """Sanity: предыдущие константы не сместились (0x17/0x18/0x19)."""
    assert lskType.lskCustomEmojiKeys == 0x17
    assert lskType.lskSearchSuggestions == 0x18
    assert lskType.lskWebviewTokens == 0x19


def test_new_lskTypes_are_ints_not_tuples() -> None:
    """gfhfyjbr регресс: lskCustomEmojiKeys был задан как (0x17,) — не повторяем."""
    for name in (
        "lskRoundPlaceholder",
        "lskInlineBotsDownloads",
        "lskMediaLastPlaybackPositions",
        "lskBotStorages",
    ):
        value = getattr(lskType, name)
        assert isinstance(value, int), (
            f"{name} must be int, got {type(value).__name__}"
        )
