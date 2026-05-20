"""Verify extend_class works on Python 3.13+ (PEP 749 dunder attributes).

Python 3.13 добавил `__firstlineno__` и `__static_attributes__` каждому классу.
Без фикса `extend_class.__new__` бьётся об конфликт этих атрибутов и крашит весь импорт.
"""
from __future__ import annotations

import sys

import pytest
from opentele.utils import extend_class, override


class BaseForTest:
    def hello(self) -> str:
        return "base"

    def shared(self) -> str:
        return "from_base"


def test_extend_class_basic() -> None:
    """Базовый смоук: extend_class добавляет метод родителю."""

    @extend_class
    class _Extension(BaseForTest):
        def new_method(self) -> str:
            return "extended"

    obj = BaseForTest()
    assert obj.hello() == "base"
    # mypy не знает про runtime extend; type: ignore нормально для теста
    assert obj.new_method() == "extended"  # type: ignore[attr-defined]


def test_extend_class_does_not_crash_on_py313_dunders() -> None:
    """На Python 3.13+ классам автоматически добавляются __firstlineno__ и
    __static_attributes__ (PEP 749). extend_class должен их игнорировать."""

    @extend_class
    class _AnotherExtension(BaseForTest):
        def another_method(self) -> int:
            return 42

    obj = BaseForTest()
    assert obj.another_method() == 42  # type: ignore[attr-defined]


@pytest.mark.skipif(sys.version_info < (3, 13), reason="dunder added in 3.13")
def test_class_has_firstlineno_on_py313() -> None:
    """На Python 3.13+ у класса должен быть __firstlineno__."""

    class Foo:
        pass

    assert hasattr(Foo, "__firstlineno__")


def test_override_decorator_validates_input() -> None:
    """@override должен ругаться только на не-функции, типом TypeError."""
    with pytest.raises(TypeError):
        override("not a function")  # type: ignore[arg-type]
