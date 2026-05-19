"""Phase 2: default app_versions modernization + deterministic generator."""
import re

import pytest

from opentele.api import API


def _major_version(s: str) -> int:
    """Извлекает major из строки вида '6.8.2 x64', '12.6.0 (6500)', '12.7'."""
    m = re.match(r"^(\d+)", s.strip())
    assert m, f"Cannot parse version from {s!r}"
    return int(m.group(1))


def test_telegram_desktop_default_app_version_is_modern() -> None:
    """TelegramDesktop default — версия 6.x+ (актуальная на 2026-05)."""
    version = API.TelegramDesktop.app_version
    major = _major_version(version)
    assert major >= 6, f"TelegramDesktop default app_version stale: {version}"


def test_telegram_desktop_default_app_version_has_x64_suffix() -> None:
    version = API.TelegramDesktop.app_version
    assert version.endswith(" x64"), f"expected ' x64' suffix, got: {version!r}"


def test_telegram_android_default_app_version_is_12_plus() -> None:
    """TelegramAndroid default — версия 12.x+ (актуальная на 2026)."""
    version = API.TelegramAndroid.app_version
    major = _major_version(version)
    assert major >= 12, f"TelegramAndroid default app_version stale: {version}"


def test_telegram_androidx_default_app_version_has_tgx_format() -> None:
    """TelegramAndroidX (Telegram X / TGX) — отдельная нумерация 0.X.Y.Z-arm64-v8a.
    Phase 2.5: после ревью переведено на правильный TGX pattern (был mainline 12.x)."""
    version = API.TelegramAndroidX.app_version
    # TGX pattern: "0.28.3.1785-arm64-v8a" (apkmirror — Telegram X stable May 2026)
    pattern = re.compile(r"^0\.\d+\.\d+\.\d+-arm64-v8a$")
    assert pattern.match(version), (
        f"TelegramAndroidX should follow TGX pattern '0.X.Y.Z-arm64-v8a': {version!r}"
    )


def test_telegram_macos_default_app_version_is_modern() -> None:
    """TelegramSwift (macOS) на 2026-05: MARKETING_VERSION = 11.15.
    Phase 2.5 после ревью обновлено с 11.13 (consvервативно) на актуальное 11.15."""
    version = API.TelegramMacOS.app_version
    major = _major_version(version)
    assert major >= 11, f"TelegramMacOS default app_version stale: {version}"


def test_telegram_ios_default_app_version_is_12_plus() -> None:
    """TelegramIOS default — версия 12.x+ (release-12.7 в TelegramMessenger/Telegram-iOS)."""
    version = API.TelegramIOS.app_version
    major = _major_version(version)
    assert major >= 12, f"TelegramIOS default app_version stale: {version}"


def test_telegram_android_default_uses_modern_device() -> None:
    """device_model должна быть Galaxy S2x или новее, не SM-G998B (S21)."""
    device = API.TelegramAndroid.device_model
    assert not device.endswith("SM-G998B"), (
        f"TelegramAndroid still uses Galaxy S21 (SM-G998B): {device}"
    )


def test_telegram_ios_default_uses_iphone_15_or_newer() -> None:
    """device_model должен быть iPhone 15/16/17 series или 16e/Air."""
    device = API.TelegramIOS.device_model
    is_modern = any(
        m in device
        for m in ("iPhone 15", "iPhone 16", "iPhone 17", "iPhone Air")
    )
    assert is_modern, f"TelegramIOS still uses old device: {device}"


# === _generate_tdesktop_app_version ===


def test_generate_app_version_returns_x64_suffix() -> None:
    v = API.TelegramDesktop._generate_tdesktop_app_version()
    assert v.endswith(" x64"), f"expected ' x64' suffix, got: {v!r}"


def test_generate_app_version_is_in_known_list() -> None:
    """Сгенерированная версия должна быть из TELEGRAM_DESKTOP_VERSIONS списка."""
    v = API.TelegramDesktop._generate_tdesktop_app_version()
    bare = v.removesuffix(" x64")
    assert bare in API.TelegramDesktop.TELEGRAM_DESKTOP_VERSIONS, (
        f"Generated version {bare!r} not in TELEGRAM_DESKTOP_VERSIONS"
    )


def test_generate_app_version_deterministic_with_unique_id() -> None:
    v1 = API.TelegramDesktop._generate_tdesktop_app_version(unique_id="test-uid-42")
    v2 = API.TelegramDesktop._generate_tdesktop_app_version(unique_id="test-uid-42")
    assert v1 == v2, f"deterministic mode must be stable: {v1!r} != {v2!r}"


def test_generate_app_version_different_unique_ids_vary() -> None:
    """20 разных unique_id дают как минимум 2 разные версии."""
    versions = {
        API.TelegramDesktop._generate_tdesktop_app_version(unique_id=f"uid-{i}")
        for i in range(20)
    }
    assert len(versions) > 1, (
        f"20 different unique_ids produced only one version — distribution broken"
    )


def test_generate_app_version_random_mode_returns_modern() -> None:
    """Random mode (no unique_id) всегда даёт major >= 5 (минимум v5.16.x)."""
    for _ in range(10):
        v = API.TelegramDesktop._generate_tdesktop_app_version()
        major = _major_version(v)
        assert major >= 5, f"random version too old: {v!r}"


def test_generate_app_version_no_legacy_v3_v4() -> None:
    """Список не должен содержать ничего из v3.x / v4.x."""
    legacy = [
        v for v in API.TelegramDesktop.TELEGRAM_DESKTOP_VERSIONS
        if v.startswith("3.") or v.startswith("4.")
    ]
    assert not legacy, f"Legacy v3.x/v4.x versions present: {legacy}"
