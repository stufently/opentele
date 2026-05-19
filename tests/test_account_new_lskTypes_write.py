"""Запись новых lskType ключей: проверяем что mapSize считается и запись производится.

Phase 1.5 update: _botStorages → _botStoragesMap (Dict), добавлен _prefsKey;
исходный substring-чек ловил ложное совпадение (_botStorages ⊂ _botStoragesMap).
"""
import inspect

from opentele.td import account as account_module


def test_account_module_writes_all_new_lskTypes() -> None:
    """В исходнике должны быть writeUInt32(lskType.lskXxx) для всех 5 новых ключей."""
    src = inspect.getsource(account_module)
    for name in (
        "lskRoundPlaceholder",
        "lskInlineBotsDownloads",
        "lskMediaLastPlaybackPositions",
        "lskBotStorages",
        "lskPrefs",  # added Phase 1.5 после ревью Codex
    ):
        marker = f"writeUInt32(lskType.{name})"
        assert marker in src, f"account.py does not write {name} into map"


def test_account_module_accounts_for_new_lskTypes_in_mapSize() -> None:
    """mapSize должен учитывать все 5 новых ключей через self._xxx атрибуты.

    Используем regex \\b границы слов чтобы избежать substring false-positives
    (например, _botStorages ⊂ _botStoragesMap).
    """
    import re

    src = inspect.getsource(account_module)
    expected_attrs = (
        "_roundPlaceholder",
        "_inlineBotsDownloads",
        "_mediaLastPlaybackPositions",
        "_botStoragesMap",  # Phase 1.5: переименован из _botStorages
        "_prefsKey",  # Phase 1.5: добавлен
    )
    for attr in expected_attrs:
        # \b — границы слова, чтобы _botStorages не матчил _botStoragesMap
        pattern = re.compile(r"self\." + re.escape(attr) + r"\b")
        assert pattern.search(src), (
            f"{attr} attribute not referenced in account.py "
            f"(possibly substring false-positive with another name)"
        )


def test_no_phantom_writeUInt32_without_writeUInt64() -> None:
    """Для каждого нового ключа должны быть writeUInt32 (типа) и writeUInt64 (значения).
    Для lskBotStorages — два writeUInt64 в цикле (FileKey + PeerId)."""
    src = inspect.getsource(account_module)
    for name in (
        "lskRoundPlaceholder",
        "lskInlineBotsDownloads",
        "lskMediaLastPlaybackPositions",
        "lskBotStorages",
        "lskPrefs",
    ):
        idx = src.find(f"writeUInt32(lskType.{name})")
        assert idx >= 0, f"writeUInt32 for {name} not found"
        # Look ahead 400 chars — у lskBotStorages длиннее (count + loop).
        snippet = src[idx : idx + 400]
        assert "writeUInt64" in snippet, (
            f"{name} writes type but not value (no writeUInt64 nearby)"
        )


def test_lskBotStorages_uses_writeUInt32_count_pattern() -> None:
    """Специально для lskBotStorages: после writeUInt32(lskBotStorages) должен идти
    второй writeUInt32 (count), а не сразу writeUInt64."""
    src = inspect.getsource(account_module)
    idx = src.find("writeUInt32(lskType.lskBotStorages)")
    assert idx >= 0
    # В следующих ~300 символах должен быть второй writeUInt32 (для count),
    # причём ДО первого writeUInt64.
    snippet = src[idx : idx + 400]
    pos_count = snippet.find("writeUInt32", len("writeUInt32(lskType.lskBotStorages)"))
    pos_u64 = snippet.find("writeUInt64")
    assert pos_count >= 0, "lskBotStorages must write count as writeUInt32"
    assert pos_count < pos_u64, (
        "Count writeUInt32 must come BEFORE first writeUInt64 (which is FileKey)"
    )


def test_lskPrefs_writes_simple_uint64() -> None:
    """lskPrefs: 1 writeUInt32 (тип) + 1 writeUInt64 (prefsKey), без счётчика."""
    src = inspect.getsource(account_module)
    idx = src.find("writeUInt32(lskType.lskPrefs)")
    assert idx >= 0
    snippet = src[idx : idx + 200]
    assert "writeUInt64(self._prefsKey)" in snippet, (
        "lskPrefs must write self._prefsKey as uint64"
    )
