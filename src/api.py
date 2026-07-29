from __future__ import annotations

import os
import platform
import typing
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from .devices import *
from .exception import *
from .utils import *

_T = TypeVar("_T")
_RT = TypeVar("_RT")


def _read_telethon_layer() -> Optional[int]:
    """MTProto layer the installed Telethon speaks, or `None`.

    Never raises: a missing or restructured Telethon must degrade to "no layer
    filtering", not break session generation.

    Module-level on purpose. `debug.IS_DEBUG_MODE` makes `BaseMetaClass` wrap
    every callable class attribute in `DebugMethod`, which re-invokes it as
    `fget(self, owner, *args)` — a `@staticmethod` then receives arguments it
    does not accept, and since the version alignment below runs at *import*
    time, that turned into `TypeError` on `import opentele.api` with debug on.
    Plain module functions are not touched by the metaclass.
    """
    try:
        from telethon.tl.alltlobjects import LAYER  # type: ignore

        return int(LAYER)
    except Exception:  # nocov - depends on the installed telethon
        return None


def _pick_versions_for_layer(
    versions: List[str], layers: Dict[str, int], layer: Optional[int]
) -> List[str]:
    """Versions from `versions` whose MTProto layer is consistent with `layer`.

    Exact matches first. If the caller's layer matches no release, pick the
    closest layer that does not overshoot it — claiming an older client than
    the wire suggests is far less conspicuous than claiming a newer one. If the
    layer is older than everything known, fall back to the *oldest* entry for
    the same reason: returning everything there would let a client on layer 180
    advertise a 7.0.x build.
    """
    if layer is None:
        return list(versions)

    exact = [v for v in versions if layers.get(v) == layer]
    if exact:
        return exact

    known = [l for v in versions if (l := layers.get(v)) is not None]
    if not known:  # nocov - table and layer map are asserted in tests
        return list(versions)

    below = [l for l in known if l < layer]
    target = max(below) if below else min(known)
    return [v for v in versions if layers.get(v) == target]


class BaseAPIMetaClass(BaseMetaClass):
    """Super high level tactic metaclass"""

    def __new__(
        cls: Type[_T], clsName: str, bases: Tuple[type], attrs: Dict[str, Any]
    ) -> _T:

        result = super().__new__(cls, clsName, bases, attrs)
        result._clsMakePID()  # type: ignore
        result.__str__ = BaseAPIMetaClass.__str__  # type: ignore

        return result

    @sharemethod
    def __str__(glob) -> str:

        if isinstance(glob, type):
            cls = glob
            result = f"{cls.__name__} {{\n"
        else:
            cls = glob.__class__
            result = f"{cls.__name__}() = {{\n"

        for attr, val in glob.__dict__.items():

            if (
                attr.startswith(f"_{cls.__base__.__name__}__")
                or attr.startswith(f"_{cls.__name__}__")
                or attr.startswith("__")
                and attr.endswith("__")
                or type(val) == classmethod
                or callable(val)
            ):
                continue

            result += f"    {attr}: {val}\n"

        return result + "}"


class APIData(object, metaclass=BaseAPIMetaClass):
    """
    API configuration to connect to `TelegramClient` and `TDesktop`

    ### Attributes:
        api_id (`int`):
            [API_ID](https://core.telegram.org/api/obtaining_api_id#obtaining-api-id)

        api_hash (`str`):
            [API_HASH](https://core.telegram.org/api/obtaining_api_id#obtaining-api-id)

        device_model (`str`):
            Device model name

        system_version (`str`):
            Operating System version

        app_version (`str`):
            Current app version

        lang_code (`str`):
            Language code of the client

        system_lang_code (`str`):
            Language code of operating system

        lang_pack (`str`):
            Language pack

    ### Methods:
        `Generate()`: Generate random device model and system version
    """

    CustomInitConnectionList: List[Union[Type[APIData], APIData]] = []

    api_id: int = None  # type: ignore
    api_hash: str = None  # type: ignore
    device_model: str = None  # type: ignore
    system_version: str = None  # type: ignore
    app_version: str = None  # type: ignore
    lang_code: str = None  # type: ignore
    system_lang_code: str = None  # type: ignore
    lang_pack: str = None  # type: ignore

    @typing.overload
    def __init__(self, api_id: int, api_hash: str) -> None:
        pass

    @typing.overload
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        device_model: str = None,
        system_version: str = None,
        app_version: str = None,
        lang_code: str = None,
        system_lang_code: str = None,
        lang_pack: str = None,
    ) -> None:
        """
        Create your own customized API

        ### Arguments:
            api_id (`int`):
                [API_ID](https://core.telegram.org/api/obtaining_api_id#obtaining-api-id)

            api_hash (`str`):
                [API_HASH](https://core.telegram.org/api/obtaining_api_id#obtaining-api-id)

            device_model (`str`, default=`None`):
                `[Device model name](API.device_model)`

            system_version (`str`, default=`None`):
                `[Operating System version](API.system_version)`

            app_version (`str`, default=`None`):
                `[Current app version](API.app_version)`

            lang_code (`str`, default=`"en"`):
                `[Language code of the client](API.app_version)`

            system_lang_code (`str`, default=`"en"`):
                `[Language code of operating system](API.system_lang_code)`

            lang_pack (`str`, default=`""`):
                `[Language pack](API.lang_pack)`

        ### Warning:
            Use at your own risk!:
                Using the wrong API can lead to your account banned.
                If the session was created using an official API, you must continue using official APIs for that session.
                Otherwise that account is at risk of getting banned.
        """

    def __init__(
        self,
        api_id: int = None,
        api_hash: str = None,
        device_model: str = None,
        system_version: str = None,
        app_version: str = None,
        lang_code: str = None,
        system_lang_code: str = None,
        lang_pack: str = None,
    ) -> None:

        Expects(
            (self.__class__ != APIData) or (api_id is not None and api_hash is not None),
            NoInstanceMatched("No instace of API matches the arguments"),
        )

        cls = self.get_cls()

        self.api_id = api_id if api_id else cls.api_id
        self.api_hash = api_hash if api_hash else cls.api_hash
        self.device_model = device_model if device_model else cls.device_model
        self.system_version = system_version if system_version else cls.system_version
        self.app_version = app_version if app_version else cls.app_version
        self.system_lang_code = (
            system_lang_code if system_lang_code else cls.system_lang_code
        )
        self.lang_pack = lang_pack if lang_pack else cls.lang_pack
        self.lang_code = lang_code if lang_code else cls.lang_code

        if self.device_model is None:
            system = platform.uname()

            if system.machine in ("x86_64", "AMD64"):
                self.device_model = "PC 64bit"
            elif system.machine in ("i386", "i686", "x86"):
                self.device_model = "PC 32bit"
            else:
                self.device_model = system.machine

        self._makePID()

    @sharemethod
    def copy(glob: Union[Type[_T], _T] = _T) -> _T:  # type: ignore

        cls = glob if isinstance(glob, type) else glob.__class__

        return cls(
            glob.api_id,  # type: ignore
            glob.api_hash,  # type: ignore
            glob.device_model,  # type: ignore
            glob.system_version,  # type: ignore
            glob.app_version,  # type: ignore
            glob.lang_code,  # type: ignore
            glob.system_lang_code,  # type: ignore
            glob.lang_pack,  # type: ignore
        )  # type: ignore

    @sharemethod
    def get_cls(glob: Union[Type[_T], _T]) -> Type[_T]:  # type: ignore
        return glob if isinstance(glob, type) else glob.__class__

    @sharemethod
    def destroy(glob: Union[Type[_T], _T]):  # type: ignore
        if isinstance(glob, type):
            return

        # might cause conflict, disabled for now, it won"t be a problem
        # if (API.findData(self.pid) is not None):
        #     API.CustomInitConnectionList.remove(self)

    def __eq__(self, __o: APIData) -> bool:
        if not isinstance(__o, APIData):
            return False
        return self.pid == __o.pid

    def __del__(self):
        self.destroy()

    @classmethod
    def _makePIDEnsure(cls) -> int:
        while True:
            pid = int.from_bytes(os.urandom(8), "little")
            if cls.findData(pid) is None:
                break
        return pid

    @classmethod
    def _clsMakePID(cls: Type[APIData]):
        cls.pid = cls._makePIDEnsure()
        cls.CustomInitConnectionList.append(cls)

    def _makePID(self):
        self.pid = self.get_cls()._makePIDEnsure()
        self.get_cls().CustomInitConnectionList.append(self)

    @classmethod
    def Generate(cls: Type[_T], unique_id: str = None) -> _T:
        """
        Generate random device model and system version

        ### Arguments:
            unique_id (`str`, default=`None`):
                The unique ID to generate - can be anything.\\
                This will be used to ensure that it will generate the same data everytime.\\
                If not set then the data will be randomized each time we runs it.
        
        ### Raises:
            `NotImplementedError`: Not supported for web browser yet

        ### Returns:
            `APIData`: Return a copy of the api with random device data

        ### Examples:
            Create a `TelegramClient` with custom API:
        ```python
            api = API.TelegramIOS.Generate(unique_id="new.session")
            client = TelegramClient(session="new.session" api=api)
            client.start()
        ```
        """
        if cls == API.TelegramAndroid or cls == API.TelegramAndroidX:
            deviceInfo = AndroidDevice.RandomDevice(unique_id)

        elif cls == API.TelegramIOS:
            deviceInfo = iOSDevice.RandomDevice(unique_id)

        elif cls == API.TelegramMacOS:
            deviceInfo = macOSDevice.RandomDevice(unique_id)

        # elif cls == API.TelegramWeb_K or cls == API.TelegramWeb_Z or cls == API.Webogram:
        else:
            raise NotImplementedError(
                f"{cls.__name__} device not supported for randomize yet"
            )

        return cls(device_model=deviceInfo.model, system_version=deviceInfo.version)

    @classmethod
    def findData(cls: Type[_T], pid: int) -> Optional[_T]:
        for x in cls.CustomInitConnectionList:  # type: ignore
            if x.pid == pid:
                return x
        return None


class API(BaseObject):
    """
    #### Built-in templates for Telegram API
    - **`opentele`** offers the ability to use **`official APIs`**, which are used by `official apps`.
    - According to [Telegram TOS](https://core.telegram.org/api/obtaining_api_id#using-the-api-id): *all accounts that sign up or log in using unofficial Telegram API clients are automatically put under observation to avoid violations of the Terms of Service*.
    - It also uses the **[lang_pack](https://core.telegram.org/method/initConnection)** parameter, of which [telethon can't use](https://github.com/LonamiWebs/Telethon/blob/master/telethon/_client/telegrambaseclient.py#L192) because it's for official apps only.
    - Therefore, **there are no differences** between using `opentele` and `official apps`, the server can't tell you apart.
    - You can use `TelegramClient.PrintSessions()` to check this out.

    ### Attributes:
        TelegramDesktop (`API`):
            Official Telegram for Desktop (Windows, macOS and Linux) [View on GitHub](https://github.com/telegramdesktop/tdesktop)

        TelegramAndroid (`API`):
            Official Telegram for Android [View on GitHub](https://github.com/DrKLO/Telegram)

        TelegramAndroidX (`API`):
            Official TelegramX for Android [View on GitHub](https://github.com/DrKLO/Telegram)

        TelegramIOS (`API`):
            Official Telegram for iOS [View on GitHub](https://github.com/TelegramMessenger/Telegram-iOS)

        TelegramMacOS (`API`):
            Official Telegram-Swift For MacOS [View on GitHub](https://github.com/overtake/TelegramSwift)

        TelegramWeb_Z (`API`):
            Default Official Telegram Web Z For Browsers [View on GitHub](https://github.com/Ajaxy/telegram-tt) | [Visit on Telegram](https://web.telegram.org/z/)

        TelegramWeb_K (`API`):
            Official Telegram Web K For Browsers [View on GitHub](https://github.com/morethanwords/tweb) | [Visit on Telegram](https://web.telegram.org/k/)

        Webogram (`API`):
            Old Telegram For Browsers [View on GitHub](https://github.com/zhukov/webogram) | [Vist on Telegram](https://web.telegram.org/?legacy=1#/im)
    """

    class TelegramDesktop(APIData):
        """
        Official Telegram for Desktop (Windows, macOS and Linux)
        [View on GitHub](https://github.com/telegramdesktop/tdesktop)

        ### Attributes:
            api_id (`int`)           : `2040`
            api_hash (`str`)         : `"b18441a1ff607e10a989891a5462e627"`
            device_model (`str`)     : `"Desktop"`
            system_version (`str`)   : `"Windows 10"`
            app_version (`str`)      : `"3.4.3 x64"`
            lang_code (`str`)        : `"en"`
            system_lang_code (`str`) : `"en-US"`
            lang_pack (`str`)        : `"tdesktop"`

        ### Methods:
            `Generate()`: Generate random device data for `Windows`, `macOS` and `Linux`
        """

        api_id = 2040
        api_hash = "b18441a1ff607e10a989891a5462e627"
        device_model = "Desktop"
        system_version = "Windows 10"
        # Phase 6: the newest STABLE Telegram Desktop speaking the same MTProto
        # layer as the installed Telethon (1.44 → layer 227 → the 6.9.x line).
        # Deliberately NOT the newest release: v7.0.x speaks layer 228, and
        # claiming a 7.0 build while invoking layer 227 is a mismatch a server
        # can see. This literal is only the fallback — it is replaced at import
        # time by `_align_desktop_version_with_telethon()` below, so the value
        # follows whichever Telethon in the supported range is installed.
        app_version = "6.9.3 x64"
        lang_code = "en"
        system_lang_code = "en-US"
        lang_pack = "tdesktop"

        @typing.overload
        @classmethod
        def Generate(
            cls: Type[_T], system: str = "windows", unique_id: str = None
        ) -> _T:
            """
            Generate random TelegramDesktop devices
            ### Arguments:
                system (`str`, default=`"random"`):
                    Which OS to generate, either `"windows"`, `"macos"`, or `"linux"`.\\
                    Default is `None` or `"random"` -  which means it will be selected randomly.
            
                unique_id (`str`, default=`None`):
                    The unique ID to generate - can be anything.\\
                    This ID will be used to ensure that it will generate the same data every single time.\\
                    If not set then the data will be randomized each time we runs it.
            
            ### Returns:
                `APIData`: Return a copy of the api with random device data
            
            ### Examples:
                Save a telethon session to tdata:
            ```python
                # unique_id will ensure that this data will always be the same (per unique_id).
                # You can use the session file name, or user_id as a unique_id.
                # If unique_id isn't specify, the device data will be randomized each time we runs it.
                oldAPI = API.TelegramDesktop.Generate(system="windows", unique_id="old.session")
                oldclient = TelegramClient("old.session", api=oldAPI)
                await oldClient.connect()

                # We can safely CreateNewSession with a different API.
                # Be aware that you should not use UseCurrentSession with a different API than the one that first authorized it.
                # You can print(newAPI) to see what it had generated.
                newAPI = API.TelegramDesktop.Generate("macos", "new_tdata")
                tdesk = oldclient.ToTDesktop(oldclient, flag=CreateNewSession, api=newAPI)

                # Save the new session to a folder named "new_tdata"
                tdesk.SaveTData("new_tdata")
            ```
            """

        @typing.overload
        @classmethod
        def Generate(cls: Type[_T], system: str = "macos", unique_id: str = None) -> _T:
            pass

        @typing.overload
        @classmethod
        def Generate(cls: Type[_T], system: str = "linux", unique_id: str = None) -> _T:
            pass

        @typing.overload
        @classmethod
        def Generate(
            cls: Type[_T], system: str = "random", unique_id: str = None
        ) -> _T:
            pass

        # Phase 6: STABLE Telegram Desktop releases, newest first, v6.0.0
        # (2025-07-31) through v7.0.6 (2026-07-27). Betas are excluded on
        # purpose — a beta build reports its version differently, so advertising
        # a beta-only number is itself a tell.
        #
        # Source: github.com/telegramdesktop/tdesktop/releases.
        TELEGRAM_DESKTOP_VERSIONS: typing.ClassVar[List[str]] = [
            "7.0.6", "7.0.5", "7.0.4", "7.0.3", "7.0.2", "7.0.1",
            "6.9.3", "6.9.2", "6.9.1", "6.9.0",
            "6.8.2", "6.8.1", "6.8.0",
            "6.7.8", "6.7.6", "6.7.5", "6.7.4", "6.7.3", "6.7.2", "6.7.1", "6.7.0",
            "6.6.2", "6.6.1", "6.6.0",
            "6.5.1", "6.5.0",
            "6.4.2", "6.4.1", "6.4.0",
            "6.3.9", "6.3.8", "6.3.7", "6.3.6", "6.3.4", "6.3.3", "6.3.2", "6.3.1", "6.3.0",
            "6.2.4", "6.2.3", "6.2.2", "6.2.0",
            "6.1.4", "6.1.3", "6.1.2", "6.1.1", "6.1.0",
            "6.0.2", "6.0.1", "6.0.0",
        ]

        # Phase 6: which MTProto layer each of those builds actually speaks,
        # read from `Telegram/SourceFiles/mtproto/scheme/api.tl` at the matching
        # release tag. This is what makes the fingerprint coherent: Telethon
        # announces a layer in `InvokeWithLayer`, and a real Telegram Desktop of
        # version X always announces the layer below. Claiming a version whose
        # layer does not match the one on the wire is a free giveaway.
        TELEGRAM_DESKTOP_LAYERS: typing.ClassVar[Dict[str, int]] = {
            "7.0.6": 228, "7.0.5": 228, "7.0.4": 228, "7.0.3": 228, "7.0.2": 228, "7.0.1": 228,
            "6.9.3": 227, "6.9.2": 227, "6.9.1": 227, "6.9.0": 227,
            "6.8.2": 225, "6.8.1": 225, "6.8.0": 225,
            "6.7.8": 224, "6.7.6": 224, "6.7.5": 224, "6.7.4": 224,
            "6.7.3": 224, "6.7.2": 224, "6.7.1": 224, "6.7.0": 224,
            "6.6.2": 223, "6.6.1": 223, "6.6.0": 223,
            "6.5.1": 222, "6.5.0": 222,
            "6.4.2": 221, "6.4.1": 221, "6.4.0": 221,
            "6.3.9": 220, "6.3.8": 220, "6.3.7": 220, "6.3.6": 220,
            "6.3.4": 218, "6.3.3": 218, "6.3.2": 218, "6.3.1": 218, "6.3.0": 218,
            "6.2.4": 216, "6.2.3": 216, "6.2.2": 216, "6.2.0": 216,
            "6.1.4": 214, "6.1.3": 214, "6.1.2": 214, "6.1.1": 214, "6.1.0": 214,
            "6.0.2": 211, "6.0.1": 211, "6.0.0": 211,
        }

        @classmethod
        def _telethon_layer(cls) -> Optional[int]:
            """MTProto layer the installed Telethon speaks, or `None`.

            Thin wrapper over the module-level `_read_telethon_layer()` — see
            the note there on why the implementation does not live in the class.
            """
            return _read_telethon_layer()

        @classmethod
        def _versions_for_layer(cls, layer: Optional[int] = None) -> List[str]:
            """Versions whose MTProto layer is consistent with `layer`.

            See `_pick_versions_for_layer()` for the selection rules.
            """
            return _pick_versions_for_layer(
                cls.TELEGRAM_DESKTOP_VERSIONS, cls.TELEGRAM_DESKTOP_LAYERS, layer
            )

        @classmethod
        def _generate_tdesktop_app_version(
            cls, unique_id: str = None, match_layer: bool = True
        ) -> str:
            """Pick a Telegram Desktop version string, e.g. `"6.9.3 x64"`.

            With `unique_id` the pick is deterministic (sha1-based), so the same
            session always reports the same version; without it, random.

            `match_layer=True` (default) narrows the pool to builds that speak
            the same MTProto layer as the installed Telethon — see
            `TELEGRAM_DESKTOP_LAYERS`. Pass `False` to draw from every known
            release, which buys entropy at the cost of that coherence.

            Idea: Paramon/opentele (`de639ac`, `41f3ea5`) for the randomized
            list, anmv/opentele for tying it to the layer; both reimplemented
            here (they hardcode the layer, this reads it from Telethon).
            """
            import hashlib
            import random as _random

            versions = (
                cls._versions_for_layer(cls._telethon_layer())
                if match_layer
                else list(cls.TELEGRAM_DESKTOP_VERSIONS)
            )
            if unique_id:
                byteid = unique_id.encode("utf-8")
                hash_id = int(hashlib.sha1(byteid).hexdigest(), 16)
                version = versions[hash_id % len(versions)]
            else:
                version = _random.choice(versions)
            return f"{version} x64"

        @classmethod
        def Generate(cls: Type[_T], system: str = None, unique_id: str = None) -> _T:

            validList = ["windows", "macos", "linux"]
            if system is None or system not in validList:
                system = SystemInfo._hashtovalue(
                    SystemInfo._strtohashid(unique_id), validList
                )

            system = system.lower()

            if system == "windows":
                deviceInfo = WindowsDevice.RandomDevice(unique_id)

            elif system == "macos":
                deviceInfo = macOSDevice.RandomDevice(unique_id)

            else:
                deviceInfo = LinuxDevice.RandomDevice(unique_id)

            return cls(
                device_model=deviceInfo.model,
                system_version=deviceInfo.version,
                app_version=cls._generate_tdesktop_app_version(unique_id),
            )

    class TelegramAndroid(APIData):
        """
        Official Telegram for Android
        [View on GitHub](https://github.com/DrKLO/Telegram)

        ### Attributes:
            api_id (`int`)           : `6`
            api_hash (`str`)         : `"eb06d4abfb49dc3eeb1aeb98ae0f581e"`
            device_model (`str`)     : `"Samsung Galaxy S25 Ultra (SM-S938)"`
            system_version (`str`)   : `"SDK 36"`
            app_version (`str`)      : `"12.9.0 (6966)"`
            lang_code (`str`)        : `"en"`
            system_lang_code (`str`) : `"en-US"`
            lang_pack (`str`)        : `"android"`
        """

        api_id = 6
        api_hash = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
        # Phase 2.5: device_model унифицирован с AndroidDevice.device_models_modern.
        # Telegram Android в initConnection отправляет marketing name + SM code.
        device_model = "Samsung Galaxy S25 Ultra (SM-S938)"
        system_version = "SDK 36"
        # Phase 6: DrKLO/Telegram `update to 12.9.0 (6966)` (2026-07-16). The
        # repo tags lag its own releases, so the version comes from the commit
        # log, which is what actually ships.
        app_version = "12.9.0 (6966)"
        lang_code = "en"
        system_lang_code = "en-US"
        lang_pack = "android"

    class TelegramAndroidX(APIData):
        """
        Official TelegramX for Android
        [View on GitHub](https://github.com/DrKLO/Telegram)

        ### Attributes:
            api_id (`int`)           : `21724`
            api_hash (`str`)         : `"3e0cb5efcd52300aec5994fdfc5bdc16"`
            device_model (`str`)     : `"Samsung SM-G998B"`
            system_version (`str`)   : `"SDK 31"`
            app_version (`str`)      : `"8.4.1 (2522)"`
            lang_code (`str`)        : `"en"`
            system_lang_code (`str`) : `"en-US"`
            lang_pack (`str`)        : `"android"`
        """

        api_id = 21724
        api_hash = "3e0cb5efcd52300aec5994fdfc5bdc16"
        # Phase 2.5 (review-fix): TelegramAndroidX (Telegram X / TGX) — distinct
        # versioning pattern "0.X.Y.Z-arm64-v8a". Current stable as of May 2026:
        # 0.28.3 (build 1785). Source: apkmirror.com/apk/telegram-fz-llc/telegram-x/
        device_model = "Samsung Galaxy S25 Ultra (SM-S938)"
        system_version = "SDK 36"
        app_version = "0.28.3.1785-arm64-v8a"
        lang_code = "en"
        system_lang_code = "en-US"
        lang_pack = "android"

    class TelegramIOS(APIData):
        """
        Official Telegram for iOS
        [View on GitHub](https://github.com/TelegramMessenger/Telegram-iOS)

        ### Attributes:
            api_id (`int`)           : `10840`
            api_hash (`str`)         : `"33c45224029d59cb3ad0c16134215aeb"`
            device_model (`str`)     : `"iPhone 17 Pro Max"`
            system_version (`str`)   : `"26.0"`
            app_version (`str`)      : `"12.9.2"`
            lang_code (`str`)        : `"en"`
            system_lang_code (`str`) : `"en-US"`
            lang_pack (`str`)        : `"ios"`
        """

        # api_id           = 8
        # api_hash         = "7245de8e747a0d6fbe11f7cc14fcc0bb"
        api_id = 10840
        api_hash = "33c45224029d59cb3ad0c16134215aeb"
        # Phase 6: newest tag in TelegramMessenger/Telegram-iOS is release-12.9.2
        # (was release-12.7 when Phase 2 landed). Device/OS unchanged.
        device_model = "iPhone 17 Pro Max"
        system_version = "26.0"
        app_version = "12.9.2"
        lang_code = "en"
        system_lang_code = "en-US"
        lang_pack = "ios"

    class TelegramMacOS(APIData):
        """
        Official Telegram-Swift For MacOS
        [View on GitHub](https://github.com/overtake/TelegramSwift)

        ### Attributes:
            api_id (`int`)           : `2834`
            api_hash (`str`)         : `"68875f756c9b437a8b916ca3de215815"`
            device_model (`str`)     : `"MacBook Pro"`
            system_version (`str`)   : `"macOS 12.0.1"`
            app_version (`str`)      : `"8.4"`
            lang_code (`str`)        : `"en"`
            system_lang_code (`str`) : `"en-US"`
            lang_pack (`str`)        : `"macos"`
        """

        api_id = 2834
        api_hash = "68875f756c9b437a8b916ca3de215815"
        # api_id = 9                                    |
        # api_hash = "3975f648bb682ee889f35483bc618d1c" | Telegram for macOS uses this api, but it's unofficial api, why?
        # Phase 2.5 (review-fix): TelegramSwift current MARKETING_VERSION = 11.15.
        # Source: github.com/overtake/TelegramSwift Telegram.xcodeproj/project.pbxproj
        # `release` branch. Releases page is sparse so version comes from project file.
        # Phase 6 re-check: unchanged — that mirror's last commit is 2025-07-29, so
        # 11.15 is still the newest number with a verifiable source. The shipping
        # macOS client is likely ahead; do not guess a number here without one.
        device_model = "MacBook Pro 14-inch M5"
        system_version = "macOS 26.0"
        app_version = "11.15"
        lang_code = "en"
        system_lang_code = "en-US"
        lang_pack = "macos"

    class TelegramWeb_Z(APIData):
        """
        Default Official Telegram Web Z For Browsers
        [View on GitHub](https://github.com/Ajaxy/telegram-tt) | [Visit on Telegram](https://web.telegram.org/z/)

        ### Attributes:
            api_id (`int`)           : `2496`
            api_hash (`str`)         : `"8da85b0d5bfe62527e5b244c209159c3"`
            device_model (`str`)     : `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"`
            system_version (`str`)   : `"Windows"`
            app_version (`str`)      : `"12.0.36 A"`
            lang_code (`str`)        : `"en"`
            system_lang_code (`str`) : `"en-US"`
            lang_pack (`str`)        : `"weba"`
        """

        api_id = 2496
        api_hash = "8da85b0d5bfe62527e5b244c209159c3"
        # Phase 6: UA refreshed to Chrome 150 (stable, Jul 2026) — the old
        # Chrome/96 string dated to 2021 and stood out on its own.
        device_model = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        # `PLATFORM_ENV` in src/util/browser/windowEnvironment.ts yields
        # "Windows" / "macOS" / "Linux" / "iOS" / "Android" — so this is right
        # as-is (unlike Web K, which sends navigator.platform, i.e. "Win32").
        system_version = "Windows"
        # Phase 6: this client is **Telegram Web A** now. `Ajaxy/telegram-tt`
        # sends `appVersion: "${APP_VERSION} ${APP_CODE_NAME}"` with
        # `APP_CODE_NAME = 'A'` and its package.json version, currently 12.0.36
        # — the old `"1.28.3 Z"` was both a stale number and the retired code
        # name. Class name kept for backwards compatibility.
        app_version = "12.0.36 A"
        lang_code = "en"
        system_lang_code = "en-US"
        # Phase 6: it *does* send a lang pack now — `LANG_PACK = 'weba'` in
        # src/config.ts. The empty string here dated to 2021, when it sent none.
        lang_pack = "weba"

    class TelegramWeb_K(APIData):
        """
        Official Telegram Web K For Browsers
        [View on GitHub](https://github.com/morethanwords/tweb) | [Visit on Telegram](https://web.telegram.org/k/)

        ### Attributes:
            api_id (`int`)           : `2496`
            api_hash (`str`)         : `"8da85b0d5bfe62527e5b244c209159c3"`
            device_model (`str`)     : `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"`
            system_version (`str`)   : `"Win32"`
            app_version (`str`)      : `"2.2"`
            lang_code (`str`)        : `"en"`
            system_lang_code (`str`) : `"en-US"`
            lang_pack (`str`)        : `"webk"`
        """

        # Phase 6: version and lang pack refreshed, credentials deliberately NOT.
        # `.env` in morethanwords/tweb does carry VITE_API_ID=1025907, but
        # `src/config/app.ts` overrides it right back for the deployment this
        # class models:
        #
        #     if(App.isMainDomain) { // use Webogram credentials then
        #       App.id = 2496; App.hash = '8da85b0d5bfe62527e5b244c209159c3';
        #
        # `MAIN_DOMAINS` being web.telegram.org / webk.telegram.org — so the real
        # Web K sends 2496, and the `.env` pair only applies to self-hosted
        # builds. `app_version` is `initConnectionParams.version`
        # (`src/lib/mtproto/networker.ts`) = VITE_VERSION verbatim: "2.2", with
        # no " K" suffix and not VITE_VERSION_FULL. `langPack: 'webk'` replaces
        # the "macos" that came from a 2021 commit of that file.
        api_id = 2496
        api_hash = "8da85b0d5bfe62527e5b244c209159c3"
        device_model = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        system_version = "Win32"
        app_version = "2.2"
        lang_code = "en"
        system_lang_code = "en-US"
        lang_pack = "webk"

    class Webogram(APIData):
        """
        Old Telegram For Browsers
        [View on GitHub](https://github.com/zhukov/webogram) | [Vist on Telegram](https://web.telegram.org/?legacy=1#/im)

        ### Attributes:
            api_id (`int`)           : `2496`
            api_hash (`str`)         : `"8da85b0d5bfe62527e5b244c209159c3"`
            device_model (`str`)     : `"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"`
            system_version (`str`)   : `"Win32"`
            app_version (`str`)      : `"0.7.0"`
            lang_code (`str`)        : `"en"`
            system_lang_code (`str`) : `"en-US"`
            lang_pack (`str`)        : `""`
        """

        api_id = 2496
        api_hash = "8da85b0d5bfe62527e5b244c209159c3"
        device_model = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
        system_version = "Win32"
        app_version = "0.7.0"
        lang_code = "en"
        system_lang_code = "en-US"
        lang_pack = ""  # The same problem as TelegramWeb_K, as TelegramWeb_K was built on Webogram


def _align_desktop_version_with_telethon() -> None:
    """Point `API.TelegramDesktop.app_version` at the installed Telethon's layer.

    The literal in the class body can only ever be right for one layer, and
    this package supports `telethon>=1.36,<2` — a range spanning many of them.
    Leaving the literal in place would advertise a 6.9.x build while the wire
    announces layer 224, which is the exact mismatch `TELEGRAM_DESKTOP_LAYERS`
    exists to prevent. The list is newest-first, so `[0]` is the newest build
    that speaks the layer we actually speak.

    The class-body literal stays as the fallback for when Telethon is missing
    or no longer exposes `LAYER`.

    Goes through the module-level helpers rather than the classmethods: with
    `debug.IS_DEBUG_MODE` on, the metaclass rewrites class callables and this
    import-time call would crash the import itself.
    """
    desktop = API.TelegramDesktop
    layer = _read_telethon_layer()
    if layer is None:  # nocov - depends on the installed telethon
        return
    candidates = _pick_versions_for_layer(
        desktop.TELEGRAM_DESKTOP_VERSIONS, desktop.TELEGRAM_DESKTOP_LAYERS, layer
    )
    if candidates:
        desktop.app_version = f"{candidates[0]} x64"


_align_desktop_version_with_telethon()


class LoginFlag(int):
    """
    Login flag for converting sessions between `TDesktop` and `TelegramClient`.

    ### Attributes:
        UseCurrentSession (LoginFlag): Use the current session.
        CreateNewSession (LoginFlag): Create a new session.

    ### Related:
        - `TDesktop.ToTelethon()`
        - `TDesktop.FromTelethon()`
        - `TelegramClient.ToTDesktop()`
        - `TelegramClient.FromTDesktop()`

    """


class UseCurrentSession(LoginFlag):
    """
    Use the current session.
    - Convert an already-logged in session of `Telegram Desktop` to `Telethon` and vice versa.
    - The "session" is just an 256-bytes `AuthKey` that get stored in `tdata folder` or Telethon `session files` [(under sqlite3 format)](https://docs.telethon.dev/en/latest/concepts/sessions.html?highlight=sqlite3#what-are-sessions).
    - `UseCurrentSession`'s only job is to read this key and convert it to one another.

    ### Warning:
        Use at your own risk!:
            You should only use the same consistant API through out the session.
            Don't use a same session with multiple different APIs, you might be banned.


    """


class CreateNewSession(LoginFlag):
    """
    Create a new session.
    - Use the `current session` to authorize the `new session` by [Login via QR code](https://core.telegram.org/api/qr-login).
    - This works just like when you signing into `Telegram` using `QR Login` on mobile devices.
    - Although `Telegram Desktop` doesn't let you authorize other sessions via `QR Code` *(or it doesn't have that feature)*, it is still available across all platforms `(``[APIs](API)``)`.

    ### Done:
        Safe to use:
            You can always use `CreateNewSessions` with any APIs, it can be different from the API that originally created the session.
    """
