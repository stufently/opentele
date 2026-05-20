"""extend_class — strict by default + opt-out через OPENTELE_EXTEND_STRICT=0.

После Phase 1.5 ревью: fail-soft (warnings.warn для ЛЮБОГО конфликта) был слишком широким —
проглатывает реальные коллизии с Telethon API. Теперь:
- strict mode (default): реальный конфликт → TypeError
- soft mode (env OPENTELE_EXTEND_STRICT=0): RuntimeWarning, продолжаем
- PEP 749 dunder ('__firstlineno__', '__static_attributes__') — отдельный crossDelete,
  не достигает конфликт-чекинга.
"""
from __future__ import annotations

import os

import pytest
from opentele.utils import extend_class


class _Parent:
    def shared_method(self) -> str:
        return "parent"


def test_strict_mode_default_raises_on_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """По умолчанию (без env-флага) — конфликт через TypeError, не warning."""
    monkeypatch.delenv("OPENTELE_EXTEND_STRICT", raising=False)

    with pytest.raises(TypeError, match=r"extend_class.*conflict"):

        @extend_class
        class _Ext(_Parent):
            def shared_method(self) -> str:  # noqa: D401
                return "extension"


def test_strict_mode_explicit_1_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPENTELE_EXTEND_STRICT=1 явно — тоже TypeError."""
    monkeypatch.setenv("OPENTELE_EXTEND_STRICT", "1")

    with pytest.raises(TypeError):

        @extend_class
        class _Ext2(_Parent):
            def shared_method(self) -> str:
                return "extension"


def test_soft_mode_warns_instead_of_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPENTELE_EXTEND_STRICT=0 — RuntimeWarning, без падения."""
    monkeypatch.setenv("OPENTELE_EXTEND_STRICT", "0")

    with pytest.warns(RuntimeWarning, match=r"extend_class.*conflict"):

        @extend_class
        class _Ext3(_Parent):
            def shared_method(self) -> str:
                return "extension"


def test_pep749_dunders_never_reach_conflict_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """В strict mode @extend_class на классе с дочерним __firstlineno__/__static_attributes__
    НЕ должен падать — эти dunder уже в crossDelete."""
    monkeypatch.delenv("OPENTELE_EXTEND_STRICT", raising=False)

    @extend_class
    class _Safe(_Parent):
        def new_method_safe(self) -> int:
            return 7

    obj = _Parent()
    assert obj.new_method_safe() == 7  # type: ignore[attr-defined]
