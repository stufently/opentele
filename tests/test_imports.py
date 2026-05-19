"""Smoke import tests — проверяют что пакет вообще импортируется на текущем Python.

Эти тесты дают самый быстрый сигнал о проблемах с зависимостями (PyQt5/PyQt6) или
с метаклассом extend_class (Py3.13+ dunder issue).
"""
import sys

import pytest


def test_python_version_supported() -> None:
    """Минимум Python 3.10 — установлено в setup.py."""
    assert sys.version_info >= (3, 10), f"Python {sys.version} too old"


def test_import_opentele() -> None:
    """Базовый импорт пакета."""
    import opentele

    assert opentele is not None


def test_import_td_subpackage() -> None:
    """Импорт td (tdata) подпакета — основной модуль для конверсии."""
    from opentele.td import Account, TDesktop

    assert TDesktop is not None
    assert Account is not None


def test_import_tl_subpackage() -> None:
    """Импорт tl (telethon) подпакета."""
    from opentele.tl import TelegramClient

    assert TelegramClient is not None


def test_import_exception_module() -> None:
    """exception.py использует QDataStream — на Py3.13 без PyQt6 это упадёт."""
    from opentele.exception import OpenTeleException, QDataStreamFailed

    assert QDataStreamFailed is not None
    assert OpenTeleException is not None


def test_no_pyqt5_in_runtime() -> None:
    """На opentele-ng не должно остаться импортов PyQt5 — только PyQt6."""
    # Просто пытаемся импортировать наши модули и проверяем, что PyQt5 не загрузилось как
    # transitive dep (если загрузилось — значит где-то в наших модулях остался импорт).
    import importlib

    import opentele
    import opentele.exception
    import opentele.td
    import opentele.tl

    # Принудительно подгружаем всё для проверки:
    importlib.import_module("opentele.utils")
    importlib.import_module("opentele.api")
    importlib.import_module("opentele.devices")

    assert "PyQt5" not in sys.modules, (
        "PyQt5 присутствует в sys.modules — где-то остался импорт. "
        "opentele-ng должен использовать только PyQt6."
    )
