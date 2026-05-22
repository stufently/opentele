from __future__ import annotations
from typing import List, Dict, Tuple, TypeVar, Type
from .utils import *
import hashlib, os

_T = TypeVar("_T")

# --- devices.json loader ------------------------------------------------
# Phase 1.2.2: device_models lists moved out of this file (was 174 KB of
# Python literals) into a single JSON blob shipped alongside as package
# data. Loaded once on import, cached in `_DATA`. Refresh via
#   `python scripts/extract_devices_data.py`.
import json as _json
from pathlib import Path as _Path

def _load_devices_json() -> dict:
    p = _Path(__file__).resolve().parent / "devices.json"
    with p.open(encoding="utf-8") as fh:
        return _json.load(fh)

_DATA = _load_devices_json()


class DeviceInfo(object):
    def __init__(self, model, version) -> None:
        self.model = model
        self.version = version

    def __str__(self) -> str:
        return f"{self.model} {self.version}"


class SystemInfo(BaseObject):

    deviceList: List[DeviceInfo] = []
    device_modesl: List[str] = []
    system_versions: List[str] = []

    def __init__(self) -> None:
        pass

    @classmethod
    def RandomDevice(cls: Type[SystemInfo], unique_id: str = None) -> DeviceInfo:
        hash_id = cls._strtohashid(unique_id)
        return cls._RandomDevice(hash_id)

    @classmethod
    def _RandomDevice(cls, hash_id: int):
        cls.__gen__()
        return cls._hashtovalue(hash_id, cls.deviceList)

    @classmethod
    def __gen__(cls):
        raise NotImplementedError(
            f"{cls.__name__} device not supported for randomize yet"
        )

    @classmethod
    def _strtohashid(cls, unique_id: str = None):

        if unique_id is not None and not isinstance(unique_id, str):
            unique_id = str(unique_id)

        byteid = os.urandom(32) if unique_id is None else unique_id.encode("utf-8")

        return int(hashlib.sha1(byteid).hexdigest(), 16) % (10 ** 12)

    @classmethod
    def _hashtorange(cls, hash_id: int, max, min=0):
        return hash_id % (max - min) + min

    @classmethod
    def _hashtovalue(cls, hash_id: int, values: List[_T]) -> _T:
        return values[hash_id % len(values)]

    @classmethod
    def _CleanAndSimplify(cls, text: str) -> str:
        return " ".join(word for word in text.split(" ") if word)


class GeneralDesktopDevice(SystemInfo):

    # Total: 794 devices, update Jan 10th 2022
    # Real device models that I crawled myself from the internet
    #
    # This is the values in HKEY_LOCAL_MACHINE\HARDWARE\DESCRIPTION\System\BIOS
    # including SystemFamily, SystemProductName, BaseBoardProduct
    #
    # Filtered any models that exceed 15 characters
    # just like tdesktop does in lib_base https://github.com/desktop-app/lib_base/blob/master/base/platform/win/base_info_win.cpp#L173
    #
    # Feel free to use
    #
    # Sources: https://answers.microsoft.com/, https://www.techsupportforum.com/ and https://www.bleepingcomputer.com/

    # device_models loaded from devices.json — see scripts/extract_devices_data.py for the source of truth.
    device_models: List[str] = _DATA["desktop"]["device_models"]


class WindowsDevice(GeneralDesktopDevice):
    # Phase 2: legacy Windows 7/8/8.1 удалены (EOL). Только современные.
    system_versions = ["Windows 11", "Windows 10"]

    deviceList: List[DeviceInfo] = []

    @classmethod
    def __gen__(cls: Type[WindowsDevice]) -> None:

        if len(cls.deviceList) == 0:

            results: List[DeviceInfo] = []

            for model in cls.device_models:
                model = cls._CleanAndSimplify(model.replace("_", ""))
                for version in cls.system_versions:
                    results.append(DeviceInfo(model, version))

            cls.deviceList = results


class LinuxDevice(GeneralDesktopDevice):

    system_versions: List[str] = []
    deviceList: List[DeviceInfo] = []

    @classmethod
    def __gen__(cls: Type[LinuxDevice]) -> None:

        if len(cls.system_versions) == 0:
            # https://github.com/desktop-app/lib_base/blob/master/base/platform/linux/base_info_linux.cpp#L129

            # ? Purposely reduce the amount of devices parameter to generate deviceList more quickly
            enviroments = [
                "GNOME",
                "MATE",
                "XFCE",
                "Cinnamon",
                "Unity",
                "ubuntu",
                "LXDE",
            ]

            wayland = ["Wayland", "XWayland", "X11"]

            libcNames = ["glibc"]
            libcVers = ["2.31", "2.32", "2.33", "2.34"]

            # enviroments = [
            #     "GNOME", "MATE", "XFCE", "Cinnamon", "X-Cinnamon",
            #     "Unity", "ubuntu", "GNOME-Classic", "LXDE"
            # ]

            # wayland = ["Wayland", "XWayland", "X11"]

            # libcNames = ["glibc", "libc"]
            # libcVers = [
            #     "2.20", "2.21", "2.22", "2.23", "2.24", "2.25", "2.26", "2.27",
            #     "2.28", "2.29", "2.30", "2.31", "2.32", "2.33", "2.34"
            # ]

            def getitem(group: List[List[str]], prefix: str = "") -> List[str]:

                prefix = "" if prefix == "" else prefix + " "
                results = []
                if len(group) == 1:
                    for item in group[0]:
                        results.append(prefix + item)
                    return results

                for item in group[0]:
                    results.extend(getitem(group[1:], prefix + item))

                return results

            libcFullNames = getitem([libcNames, libcVers], "")

            cls.system_versions = getitem(
                [enviroments, wayland, libcFullNames], "Linux"
            )

            results: List[DeviceInfo] = []

            for version in cls.system_versions:
                for model in cls.device_models:
                    results.append(DeviceInfo(model, version))

            cls.deviceList = results


class macOSDevice(GeneralDesktopDevice):

    deviceList: List[DeviceInfo] = []

    # Total: 54 device models, update Jan 10th 2022
    # Only list device models since 2013
    #
    # Sources:
    # Thanks to: https://mrmacintosh.com/list-of-mac-boardid-deviceid-model-identifiers-machine-models/
    #       and: https://github.com/brunerd/jamfTools/blob/main/EAs/macOSCompatibility.sh
    #
    # Remark: https://www.innerfence.com/howto/apple-ios-devices-dates-versions-instruction-sets

    # Phase 2.5: clean human-readable names ВМЕСТО identifier+скобки. Список
    # обходит FromIdentifier в __gen__ через флаг _skip_from_identifier_for_clean.
    # Telegram Desktop в `initConnection.device_model` отправляет marketing name
    # ("MacBook Pro M5"), а не board ID ("Mac17,2").
    # Source: Apple Support / EveryMac / AppleDB (Mac17,x — M5 series).
    # device_models loaded from devices.json — see scripts/extract_devices_data.py for the source of truth.
    device_models: List[str] = _DATA["macos"]["device_models"]

    # Phase 2.5: восстановлен префикс "macOS " — TDesktop SystemVersionPretty()
    # возвращает "macOS X.Y". Без префикса fingerprint выглядит регрессивно.
    system_versions = [
        # macOS 26 Tahoe (Sep 2025+)
        "macOS 26.0", "macOS 26.1", "macOS 26.2", "macOS 26.3", "macOS 26.4", "macOS 26.5",
        # macOS 15 Sequoia (Sep 2024+)
        "macOS 15.0", "macOS 15.1", "macOS 15.2", "macOS 15.3",
        "macOS 15.4", "macOS 15.5", "macOS 15.6", "macOS 15.7",
        # macOS 14 Sonoma (Sep 2023+) — minimum supported in Phase 2
        "macOS 14.0", "macOS 14.1", "macOS 14.2", "macOS 14.3",
        "macOS 14.4", "macOS 14.5", "macOS 14.6", "macOS 14.7",
    ]

    deviceList: List[DeviceInfo] = []

    @classmethod
    def __gen__(cls: Type[macOSDevice]) -> None:

        if len(cls.deviceList) == 0:

            # https://github.com/desktop-app/lib_base/blob/master/base/platform/mac/base_info_mac.mm#L42

            def FromIdentifier(model: str):
                words = []
                word = ""

                for ch in model:
                    if not ch.isalpha():
                        continue
                    if ch.isupper():
                        if word != "":
                            words.append(word)
                            word = ""
                    word += ch

                if word != "":
                    words.append(word)
                result = ""
                for word in words:
                    if result != "" and word != "Mac" and word != "Book":
                        result += " "
                    result += word

                return result

            # Phase 2.5: FromIdentifier нужен только для legacy board IDs формата
            # "MacBookPro16,4". Современные строки уже clean ("MacBook Pro 14-inch M5")
            # и должны проходить как есть. Признак: содержат пробел или скобки.
            def _is_legacy_board_id(s: str) -> bool:
                # Legacy: "MacBookPro16,4", "iMac20,1" — без пробелов, есть запятая.
                return "," in s and " " not in s

            new_devices_models = []
            for model in cls.device_models:
                if _is_legacy_board_id(model):
                    model = cls._CleanAndSimplify(FromIdentifier(model))
                else:
                    # Clean name — оставляем как есть, только _CleanAndSimplify (whitespace).
                    model = cls._CleanAndSimplify(model)
                if not model in new_devices_models:
                    new_devices_models.append(model)

            cls.device_models = new_devices_models

            results: List[DeviceInfo] = []

            for model in cls.device_models:
                for version in cls.system_versions:
                    results.append(DeviceInfo(model, version))

            cls.deviceList = results


class AndroidDevice(SystemInfo):

    # device_models loaded from devices.json — see scripts/extract_devices_data.py for the source of truth.
    device_models: List[str] = _DATA["android"]["device_models"]

    # Phase 2: legacy SDK 23-32 (Android 6-12) удалены. Telegram Android v12.x
    # требует Android 6+, но реалистичные fingerprints — Android 13 (SDK 33) и выше.
    system_versions = [
        "SDK 33",  # Android 13 (Aug 2022)
        "SDK 34",  # Android 14 (Oct 2023)
        "SDK 35",  # Android 15 (Oct 2024)
        "SDK 36",  # Android 16 (2025) — current stable
        "SDK 37",  # Android 17 (2026 beta)
    ]

    # Phase 2: modern flagship device list — 2024-2026 Pixel/Samsung/OnePlus/Xiaomi.
    # Phase 2.5: S26 SM-S941/S946/S948, S25 SM-S931/S936/S938 (без overlap).
    # Naming pattern: SM-S9X1 base, S9X6 plus, S9X8 ultra. SM-S731 = S25 FE.
    device_models_modern = [
        # 2026 flagships (Android 16/17) — Galaxy S26 launched March 11, 2026
        "Samsung Galaxy S26 Ultra (SM-S948)",
        "Samsung Galaxy S26+ (SM-S946)",
        "Samsung Galaxy S26 (SM-S941)",
        # 2025 flagships (Android 15/16)
        "Samsung Galaxy S25 Ultra (SM-S938)",
        "Samsung Galaxy S25+ (SM-S936)",
        "Samsung Galaxy S25 (SM-S931)",
        "Samsung Galaxy S25 Edge (SM-S937)",
        "Samsung Galaxy S25 FE (SM-S731)",
        "Google Pixel 10 Pro XL",
        "Google Pixel 10 Pro",
        "Google Pixel 10",
        # 2024 flagships (Android 14/15)
        "Samsung Galaxy S24 Ultra (SM-S928)",
        "Samsung Galaxy S24+ (SM-S926)",
        "Samsung Galaxy S24 (SM-S921)",
        "Google Pixel 9 Pro XL",
        "Google Pixel 9 Pro",
        "Google Pixel 9",
        "OnePlus 12",
        "OnePlus 13",
        "Xiaomi 14 Pro",
        "Xiaomi 15 Pro",
        "Xiaomi 15",
        # 2023 flagships (Android 14)
        "Samsung Galaxy S23 Ultra (SM-S918)",
        "Google Pixel 8 Pro",
        "Google Pixel 8",
        # 2022 flagships (Android 13)
        "Samsung Galaxy S22 Ultra (SM-S908)",
        "Google Pixel 7 Pro",
        "Google Pixel 7",
    ]

    # Привязка устройства к SDK (минимальная realistic OS).
    # Источник: Telegram Android use-cases + manufacturer support tables.
    device_models_by_sdk = {
        "SDK 37": [  # Android 17 beta — пока только Pixel 10 + S26
            "Google Pixel 10 Pro XL",
            "Google Pixel 10 Pro",
            "Google Pixel 10",
            "Samsung Galaxy S26 Ultra (SM-S948)",
            "Samsung Galaxy S26+ (SM-S946)",
            "Samsung Galaxy S26 (SM-S941)",
        ],
        "SDK 36": [  # Android 16
            "Google Pixel 10 Pro XL",
            "Google Pixel 10 Pro",
            "Google Pixel 10",
            "Google Pixel 9 Pro XL",
            "Google Pixel 9 Pro",
            "Google Pixel 9",
            "Samsung Galaxy S25 Ultra (SM-S938)",
            "Samsung Galaxy S25+ (SM-S936)",
            "Samsung Galaxy S25 (SM-S931)",
            "Samsung Galaxy S25 Edge (SM-S937)",
            "Samsung Galaxy S25 FE (SM-S731)",
            "OnePlus 13",
            "Xiaomi 15 Pro",
            "Xiaomi 15",
        ],
        "SDK 35": [  # Android 15
            "Google Pixel 9 Pro XL",
            "Google Pixel 9 Pro",
            "Google Pixel 9",
            "Samsung Galaxy S24 Ultra (SM-S928)",
            "Samsung Galaxy S24+ (SM-S926)",
            "Samsung Galaxy S24 (SM-S921)",
            "OnePlus 12",
            "Xiaomi 14 Pro",
        ],
        "SDK 34": [  # Android 14
            "Samsung Galaxy S23 Ultra (SM-S918)",
            "Google Pixel 8 Pro",
            "Google Pixel 8",
        ],
        "SDK 33": [  # Android 13
            "Samsung Galaxy S22 Ultra (SM-S908)",
            "Google Pixel 7 Pro",
            "Google Pixel 7",
        ],
    }

    deviceList: List[DeviceInfo] = []

    @classmethod
    def __gen__(cls: Type[AndroidDevice]) -> None:

        if len(cls.deviceList) == 0:

            results: List[DeviceInfo] = []

            # Phase 2.5: используем device_models_by_sdk (SDK-aware pairing) —
            # генерирует реалистичные пары "устройство 2022-2026 ↔ Android 13-17".
            # Legacy cls.device_models (~4500 моделей 2017-2022) использовать
            # с SDK 33+ нельзя — Pixel 4 + Android 17 нереалистично.
            if hasattr(cls, "device_models_by_sdk") and cls.device_models_by_sdk:
                for sdk, models in cls.device_models_by_sdk.items():
                    for model in models:
                        results.append(DeviceInfo(model, sdk))
            else:
                # Fallback (если кто-то почистил device_models_by_sdk) —
                # старый cartesian product.
                for model in cls.device_models:
                    for version in cls.system_versions:
                        results.append(DeviceInfo(model, version))

            cls.deviceList = results


class iOSDevice(SystemInfo):
    """iOS device fingerprints (Phase 2: modern flat lists).

    Source: Apple — iOS 18 (2024+), iOS 26 (2025+). Pre-iOS 18 dropped:
    iPhone 11+ supports iOS 17, iPhone XS/XR supports iOS 16. Realistic
    fingerprints for current Telegram usage — iPhone 14+ on iOS 18-26.
    """

    # iOS 18 (Sept 2024+) + iOS 26 (Sept 2025+, Apple skipped 19-25 numbering).
    system_versions = [
        # iOS 26 (Liquid Glass redesign, Sep 2025+)
        "26.0", "26.1", "26.2", "26.3", "26.4",
        # iOS 18 (Apple Intelligence, Sep 2024+)
        "18.0", "18.1", "18.2", "18.3", "18.4", "18.5", "18.6", "18.6.1", "18.6.2",
        "18.7", "18.7.1",
    ]

    # Phase 2: iPhone 17 series (Sep 2025) + iPhone Air + 16/15/14 (still common).
    # Older iPhones (12 mini, 11) dropped — non-realistic on iOS 18+.
    # device_models loaded from devices.json — see scripts/extract_devices_data.py for the source of truth.
    device_models: List[str] = _DATA["ios"]["device_models"]

    deviceList: List[DeviceInfo] = []

    @classmethod
    def __gen__(cls: Type[iOSDevice]) -> None:
        if len(cls.deviceList) == 0:
            results: List[DeviceInfo] = []
            for model in cls.device_models:
                for version in cls.system_versions:
                    results.append(DeviceInfo(model, version))
            cls.deviceList = results


# Backward compat: original opentele had this typo. Keep alias for users of upstream.
iOSDeivce = iOSDevice
