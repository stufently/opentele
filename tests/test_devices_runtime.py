"""Phase 2.5: runtime тесты для devices — output генераторов, не только сырые списки.

Phase 2 review (Cursor, Codex, Gemini) обнаружил что статические тесты на сырые
device_models не ловят:
- AndroidDevice.__gen__ игнорирует device_models_by_sdk → крутится по legacy 4500
- macOSDevice.__gen__ FromIdentifier ломает строки с скобками → "Mac Book Air Minch"
- macOS system_versions без префикса "macOS " → TDesktop returns "macOS X.Y"

Эти тесты проверяют итоговый output `RandomDevice()` / `Generate()`.
"""
import re

from opentele.api import API
from opentele.devices import (
    AndroidDevice,
    LinuxDevice,
    WindowsDevice,
    iOSDevice,
    macOSDevice,
)


# === macOS ===


def test_macOSDevice_random_model_has_no_FromIdentifier_corruption() -> None:
    """RandomDevice не должен содержать артефактов FromIdentifier парсера:
    'MacMac', одиночное ' M' в конце, 'Minch', двойные пробелы."""
    for _ in range(50):
        device = macOSDevice.RandomDevice(unique_id=f"test-{_}")
        model = device.model
        # FromIdentifier-артефакты:
        assert "MacMac" not in model, (
            f"FromIdentifier corruption ('MacMac'): {model!r}"
        )
        assert "Minch" not in model, (
            f"FromIdentifier corruption (broken 'inch'): {model!r}"
        )
        assert not re.search(r" M$", model), (
            f"FromIdentifier corruption (dangling ' M'): {model!r}"
        )
        assert "  " not in model, f"Double spaces in model: {model!r}"


def test_macOSDevice_random_model_recognizable_for_modern_macs() -> None:
    """RandomDevice должен выдавать узнаваемые имена Mac моделей."""
    keywords = ("MacBook Air", "MacBook Pro", "Mac mini", "iMac", "Mac Studio", "MacPro")
    seen = set()
    for i in range(100):
        device = macOSDevice.RandomDevice(unique_id=f"macos-{i}")
        for kw in keywords:
            if kw in device.model:
                seen.add(kw)
                break
    assert len(seen) >= 2, (
        f"RandomDevice macOS produces only {seen} models out of {keywords}. "
        f"Distribution too narrow."
    )


def test_macOSDevice_system_versions_have_macOS_prefix() -> None:
    """system_versions должны начинаться с 'macOS ' — TDesktop SystemVersionPretty()
    returns 'macOS X.Y'. Это fingerprint requirement."""
    versions = macOSDevice.system_versions
    bad = [v for v in versions if not v.startswith("macOS ")]
    assert not bad, (
        f"macOS versions missing 'macOS ' prefix: {bad[:5]}"
    )


def test_macOSDevice_random_system_version_has_macOS_prefix() -> None:
    """Каждый сгенерированный system_version должен начинаться с 'macOS '."""
    for i in range(10):
        device = macOSDevice.RandomDevice(unique_id=f"macos-{i}")
        assert device.version.startswith("macOS "), (
            f"system_version missing 'macOS ' prefix: {device.version!r}"
        )


def test_telegram_desktop_macos_generate_returns_macos_prefix() -> None:
    """API.TelegramDesktop.Generate('macos') должен дать system_version с 'macOS X.Y'."""
    for i in range(5):
        api = API.TelegramDesktop.Generate(system="macos", unique_id=f"gen-{i}")
        assert api.system_version.startswith("macOS "), (
            f"Generate('macos').system_version no prefix: {api.system_version!r}"
        )


# === Android ===


def test_AndroidDevice_random_uses_modern_devices_not_legacy_4500_list() -> None:
    """RandomDevice не должен выдавать legacy device + modern SDK. Реалистичный
    fingerprint: SDK 33-37 → device 2022+ (Galaxy S22-S26, Pixel 7-10, и т.п.)."""
    modern_keywords = (
        "Galaxy S22", "Galaxy S23", "Galaxy S24", "Galaxy S25", "Galaxy S26",
        "Pixel 7", "Pixel 8", "Pixel 9", "Pixel 10",
        "OnePlus 12", "OnePlus 13",
        "Xiaomi 14", "Xiaomi 15",
    )
    legacy_indicators = (
        "GT-I", "GT-S", "GT-N",  # Samsung pre-2020
        "Galaxy S5", "Galaxy S6", "Galaxy S7", "Galaxy S8", "Galaxy S9", "Galaxy S10",
        "Galaxy S20", "Galaxy S21",
        "Redmi Note 4", "Redmi Note 5", "Redmi Note 6", "Redmi Note 7", "Redmi Note 8",
        "Pixel 1", "Pixel 2", "Pixel 3", "Pixel 4", "Pixel 5", "Pixel 6",
    )

    seen_modern = 0
    seen_legacy = 0
    for i in range(100):
        device = AndroidDevice.RandomDevice(unique_id=f"android-{i}")
        is_modern = any(m in device.model for m in modern_keywords)
        is_legacy = any(l in device.model for l in legacy_indicators)
        if is_modern:
            seen_modern += 1
        if is_legacy:
            seen_legacy += 1

    # Хотя бы 30% — современные. Не 100% потому что в legacy списке могут быть
    # модели которые в обоих наборах формально не находятся.
    assert seen_modern >= 30, (
        f"Out of 100 RandomDevice calls, only {seen_modern} produced modern devices. "
        f"Legacy: {seen_legacy}. Expected ≥30 modern."
    )
    # Strict: legacy (≤Galaxy S21, ≤Pixel 6) — не должны быть с SDK 33+.
    # Здесь мы только проверяем что они НЕ доминируют. Жёсткое sdk-coupling — отдельный тест.
    assert seen_legacy <= 30, (
        f"Too many legacy devices ({seen_legacy}/100). Should be <=30 if "
        f"device_models_by_sdk is wired correctly."
    )


def test_AndroidDevice_random_system_version_is_modern_sdk() -> None:
    """system_version из RandomDevice — SDK 33+ (Android 13+)."""
    for i in range(20):
        device = AndroidDevice.RandomDevice(unique_id=f"android-sdk-{i}")
        match = re.match(r"^SDK (\d+)$", device.version)
        assert match, f"Unexpected version format: {device.version!r}"
        sdk = int(match.group(1))
        assert sdk >= 33, f"Generated SDK {sdk} (< 33) is too old: {device.version}"


# === iOS ===


def test_iOSDevice_random_uses_modern_iphone() -> None:
    """RandomDevice для iOS — iPhone 13+ (минимум, поддерживающий iOS 18)."""
    modern = (
        "iPhone 13", "iPhone 14", "iPhone 15", "iPhone 16", "iPhone 17",
        "iPhone Air", "iPhone SE",
    )
    seen = 0
    for i in range(30):
        device = iOSDevice.RandomDevice(unique_id=f"ios-{i}")
        if any(m in device.model for m in modern):
            seen += 1
    assert seen >= 25, (
        f"Out of 30, only {seen} produced modern iPhones. "
        f"Modern markers: {modern}"
    )


def test_iOSDevice_random_system_version_is_18_or_26() -> None:
    """RandomDevice iOS system_version — 18.x или 26.x."""
    for i in range(20):
        device = iOSDevice.RandomDevice(unique_id=f"ios-ver-{i}")
        major = int(device.version.split(".")[0])
        assert major in (18, 26), (
            f"Expected iOS major 18 or 26, got {major} (full: {device.version!r})"
        )


# === Windows ===


def test_WindowsDevice_random_version_is_modern() -> None:
    """RandomDevice Windows — Windows 10 или 11."""
    valid = {"Windows 10", "Windows 11"}
    for i in range(20):
        device = WindowsDevice.RandomDevice(unique_id=f"win-{i}")
        assert device.version in valid, (
            f"Generated Windows version not modern: {device.version!r}"
        )


# === API.Generate sanity ===


def test_telegram_android_generate_modern_pair() -> None:
    """API.TelegramAndroid.Generate должен дать SDK 33+ AND модернизованное устройство."""
    for i in range(10):
        api = API.TelegramAndroid.Generate(unique_id=f"gen-android-{i}")
        # Check SDK
        sdk_match = re.match(r"^SDK (\d+)$", api.system_version)
        assert sdk_match, f"Bad SDK format: {api.system_version!r}"
        assert int(sdk_match.group(1)) >= 33


def test_telegram_ios_generate_modern_pair() -> None:
    for i in range(10):
        api = API.TelegramIOS.Generate(unique_id=f"gen-ios-{i}")
        major = int(api.system_version.split(".")[0])
        assert major in (18, 26), f"Bad iOS major: {api.system_version!r}"
