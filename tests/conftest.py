"""Общие фикстуры pytest для всего test-suite opentele-ng."""
import pytest


@pytest.fixture
def sample_uint64() -> int:
    """Магическое 64-битное значение для round-trip тестов."""
    return 0x123456789ABCDEF0


@pytest.fixture
def big_uint64() -> int:
    """Близкое к UINT64_MAX значение — проверяем upper bound."""
    return 0xFFFFFFFFFFFFFFFE
