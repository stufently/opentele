"""Contract tests for the device-model data tables in src/devices.json.

Goal: catch the next "missing comma in upstream device list" regression
EARLIER, and lock the JSON refactor in place so a careless future edit of
devices.json doesn't silently shift fingerprint distributions or drop
device entries.
"""
from __future__ import annotations

import importlib.resources

from opentele.devices import AndroidDevice, GeneralDesktopDevice, iOSDevice, macOSDevice


def test_devices_json_is_package_data():
    """The JSON file must be shipped alongside the wheel — otherwise install
    works but `import opentele.devices` fails at import time."""
    resource = importlib.resources.files("opentele") / "devices.json"
    assert resource.is_file(), \
        f"devices.json not shipped as package data ({resource})"


def test_android_device_models_has_expected_count():
    """4870 entries after the 1.2.2 comma fix (was 4869 before). Pinning the
    count means any accidental edit to devices.json is caught."""
    assert len(AndroidDevice.device_models) == 4870


def test_desktop_macos_ios_counts_pinned():
    """Same pinning for the other three lists."""
    assert len(GeneralDesktopDevice.device_models) == 790
    assert len(macOSDevice.device_models) == 37
    assert len(iOSDevice.device_models) == 20


def test_no_implicit_string_concatenation_artifact_in_android():
    """The 1.2.2 fix at devices.py:5333 split `"Huawei MediaPad 7 Vogue"
    "Huawei LEO-BX9",` into two entries. Guard against any future edit
    that re-introduces the same class of bug (Python silently concatenates
    adjacent string literals when there's no comma between them)."""
    bogus = "Huawei MediaPad 7 VogueHuawei LEO-BX9"
    assert bogus not in AndroidDevice.device_models, \
        f"implicit-concat artifact resurrected: {bogus!r}"
    assert "Huawei LEO-BX9" in AndroidDevice.device_models, \
        "LEO-BX9 dropped from Android device list"


def test_no_zero_length_device_names():
    for collection_name, collection in (
        ("desktop", GeneralDesktopDevice.device_models),
        ("macos", macOSDevice.device_models),
        ("android", AndroidDevice.device_models),
        ("ios", iOSDevice.device_models),
    ):
        empties = [m for m in collection if not m or not m.strip()]
        assert not empties, f"{collection_name}: empty device names {empties}"


def test_no_oversized_device_names():
    """TDesktop's lib_base filter rejects names > some length. Empirically
    devices in upstream are under 60 chars; anything ≥ 100 is almost
    certainly an accidental concatenation."""
    for collection_name, collection in (
        ("desktop", GeneralDesktopDevice.device_models),
        ("macos", macOSDevice.device_models),
        ("android", AndroidDevice.device_models),
        ("ios", iOSDevice.device_models),
    ):
        oversized = [m for m in collection if len(m) >= 100]
        assert not oversized, f"{collection_name}: suspicious oversized names {oversized}"
