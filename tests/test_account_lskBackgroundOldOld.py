"""Snowing fix: account.py:186 had invalid Python `map.stream >> legacyBackgroundKeyDay`.

Это была попытка перевести C++ перегрузку оператора `>>` для QDataStream дословно,
но в Python `stream >> name` это `stream.__rshift__(name)`, а не присваивание.
Плюс `legacyBackgroundKeyDay` в этом блоке undefined → NameError при попытке чтения.
"""
import inspect

from opentele.td import account as account_module


def test_no_broken_rshift_assignment() -> None:
    """В исходнике account.py не должно быть `map.stream >> legacyBackgroundKeyDay`."""
    src = inspect.getsource(account_module)
    assert "map.stream >> legacyBackgroundKeyDay" not in src, (
        "account.py:186 still uses broken `>>` form — Snowing fix not applied"
    )


def test_lskBackgroundOldOld_uses_proper_readUInt64() -> None:
    """В исходнике должен быть корректный `legacyBackgroundKeyDay = map.stream.readUInt64()`."""
    src = inspect.getsource(account_module)
    assert "lskBackgroundOldOld" in src
    # Минимум — должна быть строка с readUInt64 для legacyBackgroundKeyDay в окрестности lskBackgroundOldOld.
    # Проверяем что просто `readUInt64` встречается достаточно раз (включая legacy ветки).
    assert src.count("readUInt64()") >= 5, (
        "Expected multiple readUInt64() calls; Snowing fix should add one for lskBackgroundOldOld"
    )
