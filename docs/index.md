# opentele-ng

**PyPI package name: [`opentele-ng`](https://pypi.org/project/opentele-ng/).**
The GitHub repository is called `opentele`, the package it publishes is
`opentele-ng`, and the import path stays `opentele`. Same project.

> **Modern fork of [thedemons/opentele](https://github.com/thedemons/opentele).**
> Python 3.10–3.14 • **pure-Python runtime, no Qt dependency** • reads tdata from current Telegram Desktop, [no version gate](#which-telegram-desktop-versions-can-it-read) • drop-in `import opentele` compatibility.

[![PyPI version](https://img.shields.io/pypi/v/opentele-ng.svg)](https://pypi.org/project/opentele-ng/)
[![Python](https://img.shields.io/pypi/pyversions/opentele-ng.svg)](https://pypi.org/project/opentele-ng/)
[![CI](https://github.com/stufently/opentele/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/stufently/opentele/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/pypi/l/opentele-ng.svg)](https://github.com/stufently/opentele/blob/main/LICENSE)

## Install

```bash
pip install opentele-ng
```

## 30-second tour

Inspect a tdata folder:

```bash
opentele-ng info /path/to/Telegram/tdata
```

Convert it to a Telethon session:

```bash
opentele-ng convert /path/to/Telegram/tdata --output ./me.session
```

For programmatic use:

```python
import asyncio
from opentele.api import API, CreateNewSession
from opentele.td import TDesktop

async def main():
    td = TDesktop("/path/to/Telegram/tdata")
    client = await td.ToTelethon(
        session="me.session",
        flag=CreateNewSession,
        api=API.TelegramDesktop.Generate(),
    )
    me = await client.get_me()
    print(me.id, me.username)

asyncio.run(main())
```

## Why this fork

Upstream `thedemons/opentele` last shipped to PyPI in January 2022 and last committed in July 2024; it started silently breaking on tdata from current Telegram Desktop because Telegram added several `lskType` keys that desync the stream on read. `opentele-ng` ships the missing wire-format fixes plus a pure-Python `QDataStream` so you don't need to install Qt — see [the README](https://github.com/stufently/opentele) for the full breakdown.

### Which Telegram Desktop versions can it read?

Verified against **Telegram Desktop 7.0.9** (2026-08-06), and nothing in the reader turns a folder away for being newer than that.

`Storage.ReadFile` checks the `TDF$` magic and the MD5 trailer, then treats the version field in the header as information — it becomes `TDesktop.AppVersion` — not as something to accept or reject. There is no floor and no ceiling. Compatibility is decided by the contents instead:

- The `lskType` enum in `td/configs.py` matches TDesktop's own in `storage_account.cpp` entry for entry, `0x00` – `0x1E`. One name lags: `0x11` is still `lskTrustedBots` here, renamed `lskTrustedPeers` upstream. Same ID, so it reads fine.
- The account-map reader dispatches `lskDraft` (`0x01`) through `lskPrefs` (`0x1E`). `lskUserMap` (`0x00`) names the map file itself and is not written as a block by either side.
- An unrecognised key **fails closed** with a clear exception instead of desyncing the stream (behaviour introduced in 1.3.0). You get an error naming the key and its offset, not silently truncated data.
- In the MTProto path the one hard equality is `MTP.Config.kVersion == 1`. `DcOptions` reads whatever positive version it finds and only writes `kVersion = 2`.

So a later Telegram Desktop could still require work here — if it adds a block type, changes the layout of an existing one, or bumps `MTP.Config` — but a version bump on its own does not.

## Where next

- [CLI quick start](examples/cli-quick-start.md) — common one-shot workflows
- [Programmatic examples](examples/convert-tdata-to-telethon.md)
- [Security policy](https://github.com/stufently/opentele/blob/main/SECURITY.md)
- [Changelog](https://github.com/stufently/opentele/blob/main/CHANGELOG.md)
- [Benchmarks](https://github.com/stufently/opentele/blob/main/BENCHMARKS.md)
