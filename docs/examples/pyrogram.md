# Pyrogram ↔ tdata

`opentele-ng` converts `tdata` to and from [Pyrogram](https://docs.pyrogram.org)
sessions, in addition to Telethon.

Pyrogram is an **optional** dependency:

```bash
pip install "opentele-ng[pyrogram]"
```

That pulls [`pyrofork`](https://pypi.org/project/pyrofork/), the maintained
distribution of the `pyrogram` package. Vanilla `pyrogram` and `kurigram`
provide the same import name and work as well. Nothing is imported unless you
call one of the methods below, so a plain `pip install opentele-ng` is
unaffected.

## tdata → Pyrogram

```python
import asyncio
from opentele.api import API
from opentele.td import TDesktop


async def main() -> None:
    tdesk = TDesktop(r"C:\Users\<user>\AppData\Roaming\Telegram Desktop\tdata")

    # Reuses the existing authorization — no QR, no OTP.
    client = await tdesk.ToPyrogram(api=API.TelegramDesktop)

    async with client:
        print(await client.get_me())


asyncio.run(main())
```

The returned client is in-memory by default, so nothing is written to disk. To
get a `.session` file instead:

```python
client = await tdesk.ToPyrogram(name="me", in_memory=False, workdir="/tmp/sessions")
```

That writes `<name>.session` in `workdir`. Omit `workdir` and the file lands
next to your entry script (`sys.argv[0]`'s directory, Pyrogram's default) —
**not** in the process CWD. If the file already exists you get
`FileExistsError`: Pyrogram would keep its `peers` / `usernames` /
`update_state` tables and the new session would inherit the previous account's
cached contacts. Pass `overwrite=True` to replace the file outright, or pick
another `name`.

Any other keyword goes straight to `pyrogram.Client`, e.g. `proxy={...}`.

With `flag=CreateNewSession` the QR login is performed by an internal Telethon
client, and `**kwargs` never reach it — Telethon and Pyrogram disagree on the
shape of `proxy` (tuple vs dict). Configure that leg separately, or the
authorization goes out over a direct connection:

```python
client = await tdesk.ToPyrogram(
    flag=CreateNewSession,
    api=API.TelegramAndroid,
    proxy={"scheme": "socks5", "hostname": "127.0.0.1", "port": 9050},
    telethon_kwargs={"proxy": ("socks5", "127.0.0.1", 9050)},
)
```

### `app_version` follows Pyrogram's MTProto layer

Pyrogram ships its own generated schema, so it announces a different layer than
Telethon (pyrofork 2.3.69 → 220, Telethon 1.44 → 227). A Telegram Desktop
`app_version` is therefore re-derived for Pyrogram's layer, so the version you
claim matches the layer on the wire. Pass `align_layer=False` to keep
`api.app_version` exactly as given. Android / iOS / web fingerprints are never
touched.

### Why this path carries a better fingerprint than Telethon

Telethon cannot set `lang_pack`, which every official client sends. Pyrogram
accepts it, so `ToPyrogram()` puts the **whole** `APIData` fingerprint on the
wire — `api_id`, `api_hash`, `device_model`, `system_version`, `app_version`,
`lang_code`, `system_lang_code` **and** `lang_pack`.

## Pyrogram → tdata

```python
import asyncio
from opentele.td import TDesktop
from pyrogram import Client


async def main() -> None:
    client = Client("my_account", api_id=..., api_hash=...)

    tdesk = await TDesktop.FromPyrogram(client)
    tdesk.SaveTData("new_tdata")


asyncio.run(main())
```

The client does not need to be connected — credentials are read from its
storage (and the storage is left exactly as it was found: opened only if it was
closed, and closed again afterwards).

It does need to be a session `tdata` can represent:

| Session | Result |
|---------|--------|
| Authorized user session | converted |
| No `auth_key` | `PyrogramUnauthorized` — nothing to convert |
| Test-DC session (`test_mode`) | `PyrogramSessionUnsupported` — `tdata` written here always carries the production MTP config, so the key would be dead |
| Bot session (`is_bot`) | `PyrogramSessionUnsupported` — Telegram Desktop cannot sign in as a bot |

## Login flags

| Flag | `ToPyrogram()` | `FromPyrogram()` |
|------|----------------|------------------|
| `UseCurrentSession` (default) | ✅ reuses the existing authorization | ✅ |
| `CreateNewSession` | ✅ QR-authorizes a new session through the Telethon path first, then converts it | ❌ `LoginFlagInvalid` |

`CreateNewSession` is what you want when the target API differs from the one
that created the `tdata` — reusing a session across APIs is what gets accounts
flagged. See [Using official APIs](using-official-apis.md).

`FromPyrogram()` has no `CreateNewSession`: Pyrogram has no equivalent of
Telethon's `QRLoginToNewClient()` here, so there is no way to mint a second
session from the first. Convert to Telethon first if you need it.
