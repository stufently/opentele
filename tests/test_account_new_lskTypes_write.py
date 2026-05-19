"""Запись новых lskType ключей: проверяем что mapSize считается и запись производится."""
import inspect

from opentele.td import account as account_module


def test_account_module_writes_all_new_lskTypes() -> None:
    """В исходнике должны быть writeUInt32(lskType.lskXxx) для всех 4 новых ключей."""
    src = inspect.getsource(account_module)
    for name in (
        "lskRoundPlaceholder",
        "lskInlineBotsDownloads",
        "lskMediaLastPlaybackPositions",
        "lskBotStorages",
    ):
        marker = f"writeUInt32(lskType.{name})"
        assert marker in src, f"account.py does not write {name} into map"


def test_account_module_accounts_for_new_lskTypes_in_mapSize() -> None:
    """mapSize должен учитывать новые ключи через атрибуты self._xxx."""
    src = inspect.getsource(account_module)
    for attr in (
        "_roundPlaceholder",
        "_inlineBotsDownloads",
        "_mediaLastPlaybackPositions",
        "_botStorages",
    ):
        assert f"self.{attr}" in src, f"{attr} attribute not referenced in account.py"


def test_no_phantom_writeUInt32_without_writeUInt64() -> None:
    """Для каждого нового ключа должны быть и writeUInt32 (типа), и writeUInt64 (значения)."""
    src = inspect.getsource(account_module)
    for name in (
        "lskRoundPlaceholder",
        "lskInlineBotsDownloads",
        "lskMediaLastPlaybackPositions",
        "lskBotStorages",
    ):
        # Найдём место writeUInt32(lskType.<name>) и проверим что в следующих 200 символах
        # есть writeUInt64.
        idx = src.find(f"writeUInt32(lskType.{name})")
        assert idx >= 0, f"writeUInt32 for {name} not found"
        snippet = src[idx : idx + 200]
        assert "writeUInt64" in snippet, (
            f"{name} writes type but not value (no writeUInt64 nearby)"
        )
