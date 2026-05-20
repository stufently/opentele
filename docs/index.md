# opentele-ng

> **Modern fork of [thedemons/opentele](https://github.com/thedemons/opentele).**
> Python 3.10–3.14 • **pure-Python runtime, no Qt dependency** • reads current Telegram Desktop 5.x–6.x tdata format • drop-in `import opentele` compatibility.

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

Upstream `thedemons/opentele` was last touched in 2022 and started silently breaking on tdata from current Telegram Desktop (5.x–6.x) because Telegram added several `lskType` keys that desync the stream on read. `opentele-ng` ships the missing wire-format fixes plus a pure-Python `QDataStream` so you don't need to install Qt — see [the README](https://github.com/stufently/opentele) for the full breakdown.

## Where next

- [CLI quick start](examples/cli-quick-start.md) — common one-shot workflows
- [Programmatic examples](examples/convert-tdata-to-telethon.md)
- [Security policy](https://github.com/stufently/opentele/blob/main/SECURITY.md)
- [Changelog](https://github.com/stufently/opentele/blob/main/CHANGELOG.md)
- [Benchmarks](https://github.com/stufently/opentele/blob/main/BENCHMARKS.md)
