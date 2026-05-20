"""Phase 1.5 fix: `isinstance(cls, type)` → `isinstance(decorated_cls, type)`.

Upstream проверял `cls` — это metaclass `extend_class` (всегда type), проверка
бесполезна. Реальный кейс: применить decorator не к классу — должен упасть TypeError.
"""
import pytest
from opentele.utils import extend_class


def test_extend_class_rejects_non_class() -> None:
    """@extend_class на функции — TypeError."""

    def some_func() -> None:
        pass

    with pytest.raises(TypeError, match=r"only for classes"):
        extend_class(some_func)  # type: ignore[arg-type]


def test_extend_class_rejects_instance() -> None:
    """@extend_class на инстансе — TypeError."""

    class Foo:
        pass

    instance = Foo()
    with pytest.raises(TypeError, match=r"only for classes"):
        extend_class(instance)  # type: ignore[arg-type]


def test_extend_class_accepts_class() -> None:
    """@extend_class на классе — OK."""

    class Parent:
        pass

    @extend_class
    class Extension(Parent):
        def added(self) -> int:
            return 42

    obj = Parent()
    assert obj.added() == 42  # type: ignore[attr-defined]
