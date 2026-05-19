"""2026-aware device fingerprint coverage tests (Phase 2).

Проверяет что system_versions и device_models содержат актуальные на 2026-05
устройства и ОС. Источник: dev branches Apple iOS / Android / TDesktop.
"""
from opentele.devices import (
    AndroidDevice,
    WindowsDevice,
    macOSDevice,
)


def _get_ios_class():
    """iOSDevice появилось в Phase 2 (правильное имя); iOSDeivce — legacy alias."""
    from opentele import devices as devices_mod

    cls = getattr(devices_mod, "iOSDevice", None) or getattr(devices_mod, "iOSDeivce", None)
    assert cls is not None, "Neither iOSDevice nor iOSDeivce found in opentele.devices"
    return cls


def test_macOS_system_versions_includes_tahoe_26() -> None:
    """macOS 26 Tahoe (Sep 2025+) должна быть в списке версий.
    Phase 2.5: формат "macOS X.Y" (с префиксом — TDesktop SystemVersionPretty)."""
    versions = macOSDevice.system_versions
    assert any("26." in v for v in versions), (
        f"macOS 26 (Tahoe) missing from system_versions; first 5: {versions[:5]}"
    )


def test_macOS_system_versions_includes_sequoia_15() -> None:
    """macOS 15 Sequoia (Sep 2024+) тоже должна быть."""
    versions = macOSDevice.system_versions
    assert any("15." in v for v in versions), (
        f"macOS 15 (Sequoia) missing: {versions[:8]}"
    )


def test_macOS_device_models_include_apple_silicon_m4_or_m5() -> None:
    """Хотя бы один M4 или M5 mac должен быть в device_models."""
    models = macOSDevice.device_models
    assert any("M4" in m or "M5" in m for m in models), (
        f"Modern Apple Silicon (M4 or M5) missing from macOS device_models; "
        f"first 5: {models[:5]}"
    )


def test_macOS_drops_legacy_pre_sonoma() -> None:
    """macOS 10.x – 13.x — EOL; не должно быть в списке.
    Phase 2.5: проверяем по "macOS 10.", "macOS 11." и т.д. (с префиксом)."""
    versions = macOSDevice.system_versions
    legacy = [
        v for v in versions
        if any(p in v for p in ("macOS 10.", "macOS 11.", "macOS 12.", "macOS 13."))
    ]
    assert not legacy, (
        f"Legacy macOS versions still present (10.x-13.x): {legacy}"
    )


def test_iOS_device_models_include_iphone_17_or_air() -> None:
    iOSCls = _get_ios_class()
    models = iOSCls.device_models
    has_modern = any("iPhone 17" in m or "iPhone Air" in m for m in models)
    assert has_modern, f"iPhone 17 / iPhone Air missing from iOS device_models"


def test_iOS_system_versions_includes_ios_26() -> None:
    """iOS 26 (Sept 2025+) должна быть в списке."""
    iOSCls = _get_ios_class()
    versions = iOSCls.system_versions
    assert any(v.startswith("26.") for v in versions), (
        f"iOS 26 missing from system_versions; first 5: {versions[:5]}"
    )


def test_iOS_drops_legacy_pre_18() -> None:
    """iOS 17 и ниже больше не актуальны для свежих iPhone'ов."""
    iOSCls = _get_ios_class()
    versions = iOSCls.system_versions
    legacy = [
        v for v in versions
        if any(v.startswith(p) for p in ("15.", "16.", "17."))
    ]
    assert not legacy, f"Legacy iOS versions (15-17) still present: {legacy}"


def test_iOSDevice_alias_for_typo() -> None:
    """iOSDeivce — legacy typo, должен остаться как alias для backward compat."""
    from opentele.devices import iOSDeivce, iOSDevice  # noqa: F401

    assert iOSDeivce is iOSDevice


def test_android_system_versions_include_sdk_36_or_37() -> None:
    versions = AndroidDevice.system_versions
    assert "SDK 36" in versions or "SDK 37" in versions, (
        f"Android 16 (SDK 36) / 17 (SDK 37) missing: {versions}"
    )


def test_android_system_versions_drops_sdk_below_33() -> None:
    """SDK 32 и ниже (Android 12 и ниже) — устаревшие."""
    versions = AndroidDevice.system_versions
    legacy = [v for v in versions if v.startswith("SDK ") and int(v[4:]) < 33]
    assert not legacy, f"Legacy Android SDKs still present: {legacy}"


def _all_android_models() -> list[str]:
    """Собирает все android модели независимо от структуры (list или dict)."""
    result: list[str] = []
    if hasattr(AndroidDevice, "device_models"):
        models = AndroidDevice.device_models
        if isinstance(models, dict):
            for lst in models.values():
                result.extend(lst)
        else:
            result.extend(models)
    if hasattr(AndroidDevice, "device_models_by_sdk"):
        for lst in AndroidDevice.device_models_by_sdk.values():
            result.extend(lst)
    return result


def test_android_device_models_include_pixel_10_or_s25_or_s26() -> None:
    """2025-2026 Android flagships."""
    models = _all_android_models()
    flagship_markers = ["Pixel 10", "S25", "S26"]
    has_flagship = any(any(m in model for m in flagship_markers) for model in models)
    assert has_flagship, (
        f"2025-2026 Android flagships (Pixel 10 / Galaxy S25 / S26) missing. "
        f"Total models: {len(models)}"
    )


def test_windows_versions_only_modern() -> None:
    """Windows 7/8/8.1 — EOL; должны быть только 10/11."""
    versions = WindowsDevice.system_versions
    legacy = {"Windows 7", "Windows 8", "Windows 8.1"} & set(versions)
    assert not legacy, f"Legacy Windows versions still present: {legacy}"
    assert "Windows 11" in versions, "Windows 11 missing"
    assert "Windows 10" in versions, "Windows 10 missing"
