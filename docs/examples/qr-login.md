# QR-code login

Authorise a new Telegram session via the QR-code shown in the official Telegram
app (Settings → Devices → Link Desktop Device) **without phone OTP** in the
script. (2FA cloud-password accounts still need the password — see section
below.) No tdata to import either — `opentele-ng` will create the session from
scratch on the user's confirmation.

The flow uses **Telethon** under the hood (`TelegramClient.qr_login`); the
`opentele.tl.TelegramClient` adds the bridge so the session can later be saved
as tdata or further converted.

## Requirements

- A registered Telegram account on a phone with an active Telegram app.
- `opentele-ng >= 0.3.0` (Phase 3+).

## Minimal example

```python
import asyncio
import qrcode  # pip install qrcode

from opentele.api import API
from opentele.tl import TelegramClient


async def main() -> None:
    # 1. Pick (or generate) an API. Use a desktop API id/hash here.
    api = API.TelegramDesktop.Generate(unique_id="my-machine")
    client = TelegramClient(session="qr-demo", api=api)

    # 2. Connect and start the QR-login handshake.
    await client.connect()
    qr_login = await client.qr_login()

    # 3. Render the QR URL to the terminal. The user opens Telegram on the phone
    #    and points the camera at the printed QR.
    qr = qrcode.QRCode()
    qr.add_data(qr_login.url)
    qr.print_ascii(invert=True)

    print("Scan the QR code shown above in the Telegram app to log in.")

    # 4. Wait for the user to confirm. If the QR expires, recreate it.
    await qr_login.wait()

    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username})")

    await client.disconnect()


asyncio.run(main())
```

## 2-factor authentication (cloud password)

If the account has 2FA enabled, `qr_login.wait()` raises
`telethon.errors.SessionPasswordNeededError`. Catch it and call
`client.sign_in(password=...)` once:

```python
from telethon.errors import SessionPasswordNeededError

try:
    await qr_login.wait()
except SessionPasswordNeededError:
    password = input("2FA cloud password: ")
    await client.sign_in(password=password)
```

## Converting the QR-created session to tdata

After authorisation, `client` holds a Telethon session. Convert it to `tdata`
(Telegram Desktop format) with `TDesktop.FromTelethon`:

```python
from opentele.api import API, CreateNewSession
from opentele.td import TDesktop
from opentele.tl import TelegramClient


async def to_tdata() -> None:
    api = API.TelegramDesktop.Generate(unique_id="qr-imported")
    client = TelegramClient("qr-demo", api=api)
    await client.connect()
    # ... (QR login flow, as above) ...

    desktop_api = API.TelegramDesktop.Generate(unique_id="desktop-tdata")
    tdesk = await TDesktop.FromTelethon(
        client,
        flag=CreateNewSession,
        api=desktop_api,
        # 2FA-protected accounts: pass `password=` so the bridge can
        # complete `sign_in` after QRLoginToNewClient raises
        # SessionPasswordNeededError. Without it the conversion fails.
        password="cloud-password-here",  # or None for non-2FA accounts
    )

    tdesk.SaveTData("my_tdata_folder")
    print("tdata saved to my_tdata_folder/")
```

Phase 3 update — `FromTelethon` accepts `**kwargs` that are forwarded to the
underlying `QRLoginToNewClient`, useful for passing a proxy or custom
connection class:

```python
from telethon.network.connection import ConnectionTcpFull

tdesk = await TDesktop.FromTelethon(
    client,
    flag=CreateNewSession,
    api=desktop_api,
    connection=ConnectionTcpFull,
    proxy=("socks5", "127.0.0.1", 9050),
)
```

## Caveats

- QR-login is a Telethon flow. Phone OTP and SMS auth methods bypass it.
- The QR-code URL expires after ~30 seconds. Re-call `client.qr_login()` to refresh.
- The Telegram app on the phone needs network access to the same Telegram DC
  during the handshake. Corporate proxies that mangle TLS may break the flow.
- 2FA password input via `input()` is not safe for production scripts; route it
  through your secret manager.

## See also

- [Telethon QR Login API](https://docs.telethon.dev/en/stable/quick-references/objects-reference.html#telethon.client.auth.AuthMethods.qr_login)
- [Telegram FAQ: Link Desktop Device](https://telegram.org/faq#q-can-i-have-telegram-on-my-pc-mac)
- `opentele/tl/telethon.py: QRLoginToNewClient` — the bridge used by
  `TDesktop.FromTelethon`.
