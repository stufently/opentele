"""Smoke-проверки внешних зависимостей opentele-ng.

После Phase 1.5: `tgcrypto-pyrofork` — drop-in replacement для `tgcrypto`. Здесь
проверяем, что нужные функции присутствуют и AES-IGE даёт ожидаемый roundtrip.
"""
import os

import pytest


def test_tgcrypto_module_imports_with_ige_functions() -> None:
    """import tgcrypto должен дать `ige256_encrypt` и `ige256_decrypt`."""
    import tgcrypto

    assert hasattr(tgcrypto, "ige256_encrypt"), (
        "tgcrypto must provide ige256_encrypt (used by storage.py)"
    )
    assert hasattr(tgcrypto, "ige256_decrypt"), (
        "tgcrypto must provide ige256_decrypt (used by storage.py)"
    )


@pytest.mark.parametrize("payload_size", [16, 32, 64, 128, 256])
def test_aes_ige_roundtrip(payload_size: int) -> None:
    """AES-256 IGE roundtrip: encrypt → decrypt → bytes идентичны."""
    import tgcrypto

    key = os.urandom(32)
    iv = os.urandom(32)
    plaintext = os.urandom(payload_size)

    encrypted = tgcrypto.ige256_encrypt(plaintext, key, iv)
    decrypted = tgcrypto.ige256_decrypt(encrypted, key, iv)

    assert decrypted == plaintext, (
        f"AES-IGE roundtrip failed for {payload_size}-byte payload: "
        f"input != output after encrypt+decrypt"
    )
    assert encrypted != plaintext, "Ciphertext must differ from plaintext (sanity)"


def test_telethon_version_is_v1() -> None:
    """telethon должен быть в диапазоне 1.36..<2 — pin'ы в requirements.txt."""
    import telethon

    version = telethon.__version__
    major = int(version.split(".")[0])
    assert major == 1, (
        f"Expected telethon 1.x (pin telethon<2), got {version}. "
        f"Phase 1.5 фиксирует upper bound до явной проверки 2.x"
    )


def test_pyqt6_is_active_qt_binding() -> None:
    """Активен должен быть PyQt6, не PyQt5/PySide6."""
    from PyQt6 import QtCore

    assert QtCore is not None
    # Sanity: enum-стиль PyQt6 — QDataStream.Status.Ok, не QDataStream.Ok.
    assert hasattr(QtCore.QDataStream, "Status"), "PyQt6 enum style expected"
