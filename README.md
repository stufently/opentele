<!-- vim: syntax=Markdown -->

# opentele-ng

> **opentele-ng** — modern fork of [thedemons/opentele](https://github.com/thedemons/opentele) for **Python 3.10 – 3.13** (Python 3.14 — experimental, while 3.14 itself is in active development). Reads current Telegram Desktop 5.x – 6.x tdata format with the 2024-2025 storage keys (`lskRoundPlaceholder` 0x1A, `lskInlineBotsDownloads` 0x1B, `lskMediaLastPlaybackPositions` 0x1C, `lskBotStorages` 0x1D as `Dict[PeerId, FileKey]`, `lskPrefs` 0x1E). Migrated to PyQt6 and `tgcrypto-pyrofork`. Import name remains `opentele` for drop-in compatibility.

## Install

```bash
pip install opentele-ng
```

```python
from opentele.td import TDesktop
from opentele.tl import TelegramClient
```

## Credits

See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for upstream and contributor credits (thedemons, RobertAzovski, Snowing, azamtoiri, hustLer2k, iamlostshe).

## Configuration

- `OPENTELE_EXTEND_STRICT=0` — switches `@extend_class` decorator to soft mode (RuntimeWarning instead of TypeError on attribute conflicts). Default: strict.

## Status

Phase 1 + 1.5 of modernization: package installs and loads current Telegram Desktop 5.x – 6.x tdata without data loss across Python 3.10 – 3.13 (3.14 experimental). Phase 4 (golden roundtrip tests) and Phase 5 (drop PyQt for pure-Python QDataStream → `opentele-ng 1.0.0`) are upcoming. See [CHANGELOG.md](CHANGELOG.md).

<p align="center">
<img src="https://raw.githubusercontent.com/thedemons/opentele/main/opentele.png" alt="logo" width="180"/>
</p>

<br>

A **Python Telegram API Library** for converting between **tdata** and **telethon** sessions, with built-in **official Telegram APIs**. [**Read the upstream documentation**](https://opentele.readthedocs.io/en/latest/documentation/telegram-desktop/tdesktop/).

# NOTICE
Unfortunately, due to the lack of interest, I can no longer maintain this project and keep it up-to-date with the latest version of Telegram Desktop and Telethon.
<br>
If you have been using opentele for a while, I appreciate it, please consider contributing to the project, ask any questions in [Discussion](https://github.com/thedemons/opentele/discussions) and I'll try to help.

## Features
- Convert [Telegram Desktop](https://github.com/telegramdesktop/tdesktop) **tdata** sessions to [telethon](https://github.com/LonamiWebs/Telethon) sessions and vice versa.
- Use **telethon** with [official APIs](#authorization) to avoid bot detection.
- Randomize [device info](https://opentele.readthedocs.io/en/latest/documentation/authorization/api/#generate) using real data that recognized by Telegram server.

## Dependencies

- [telethon](https://github.com/LonamiWebs/Telethon) - Widely used Telegram's API library for Python.
- [tgcrypto](https://github.com/pyrogram/tgcrypto) - AES-256-IGE encryption to works with `tdata`.
- [pyQt5](https://www.riverbankcomputing.com/software/pyqt/) - Used by Telegram Desktop to streams data from files.

## Installation
- Install from [PyPI](https://pypi.org/project/opentele/):
```pip title="pip"
pip install --upgrade opentele
```

## First Run
Load TDesktop from tdata folder and convert it to telethon, with a custom API:
```python
from opentele.td import TDesktop
from opentele.tl import TelegramClient
from opentele.api import API, CreateNewSession, UseCurrentSession
import asyncio

async def main():
    
    # Load TDesktop client from tdata folder
    tdataFolder = r"C:\Users\<username>\AppData\Roaming\Telegram Desktop\tdata"
    tdesk = TDesktop(tdataFolder)

    # Using official iOS API with randomly generated device info
    # print(api) to see more
    api = API.TelegramIOS.Generate()

    # Convert TDesktop session to telethon client
    # CreateNewSession flag will use the current existing session to
    # authorize the new client by `Login via QR code`.
    client = await tdesk.ToTelethon("newSession.session", CreateNewSession, api)

    # Although Telegram Desktop doesn't let you authorize other
    # sessions via QR Code (or it doesn't have that feature),
    # it is still available across all platforms (APIs).

    # Connect and print all logged in devices
    await client.connect()
    await client.PrintSessions()

asyncio.run(main())
```

## Authorization
**opentele** offers the ability to use **official APIs**, which are used by official apps. You can check that out [here](https://opentele.readthedocs.io/en/latest/documentation/authorization/api/#class-api).
<br>

According to [Telegram TOS](https://core.telegram.org/api/obtaining_api_id#using-the-api-id): *all accounts that sign up or log in using unofficial Telegram API clients are automatically put under observation to avoid violations of the Terms of Service*.
<br>
<br>
It also uses the **[lang_pack](https://core.telegram.org/method/initConnection)** parameter, of which [telethon can't use](https://github.com/LonamiWebs/Telethon/blob/dd51aea4db90fd255a14e27192e221c70b45e105/telethon/_client/telegrambaseclient.py#L197) because it's for official apps only.
<br>
Therefore, **there are no differences** between using opentele and official apps, the server can't tell you apart.

## Incoming Features
- [x] Writing data to tdata for converting telethon sessions to tdesktop.
- [x] Random device information for [initConnection](https://core.telegram.org/method/initConnection) to avoid spam-detection.
- [ ] Add support for [pyrogram](https://github.com/pyrogram/pyrogram).
- [ ] Develop opentele-tui using [textual](https://github.com/Textualize/textual) for non-experience user.

## Examples
The best way to learn anything is by looking at the examples. Am I right?

- Example on [readthedocs](https://opentele.readthedocs.io/en/latest/examples/)
- Example on [github](./examples)

## Documentation [![documentation](https://readthedocs.org/projects/opentele/badge/?version=latest&style=flat)](https://opentele.readthedocs.io/)
- Read documentation on [readthedocs](https://opentele.readthedocs.io/en/latest/documentation/telegram-desktop/tdesktop/)
- Read documentation on [github](https://github.com/thedemons/opentele/tree/main/docs-github)
