<!-- vim: syntax=Markdown -->

# opentele-ng

> **Modern fork of [thedemons/opentele](https://github.com/thedemons/opentele).**
> Python 3.10 – 3.14 • **pure-Python runtime, no Qt dependency** •
> reads current Telegram Desktop 5.x – 6.x tdata format • drop-in
> `import opentele` compatibility.

[![PyPI version](https://img.shields.io/pypi/v/opentele-ng.svg)](https://pypi.org/project/opentele-ng/)
[![Python](https://img.shields.io/pypi/pyversions/opentele-ng.svg)](https://pypi.org/project/opentele-ng/)
[![CI](https://github.com/stufently/opentele/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/stufently/opentele/actions/workflows/ci.yml)
[![Lint](https://github.com/stufently/opentele/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/stufently/opentele/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/pypi/l/opentele-ng.svg)](LICENSE)
![No Qt](https://img.shields.io/badge/runtime-no%20Qt%20dependency-brightgreen)

## Why this fork

Upstream `thedemons/opentele` was last touched in 2022. By mid-2026 it stopped
working on modern Python (3.13+ broke the metaclass), missed several `lskType`
keys added to tdata in 2024-2025 (silently dropping data on read), shipped
stale device fingerprints, and required ~50 MB of PyQt5 wheels just to parse
binary streams.

`opentele-ng` is a clean-room modernization done over 11 release phases with
3-AI code review (OpenAI Codex, Cursor, Google Gemini) at every milestone.
None of the 132 community forks of upstream attempted the pure-Python rewrite —
this one ships it.

## Highlights

| Phase | What |
|------|------|
| **Phase 5** | **Pure-Python `QDataStream` / `QByteArray` / `QFile` / `QBuffer`** — byte-identical to PyQt6 (17 byte-for-byte equivalence tests + 247 integration tests). PyQt6 removed from runtime, install is now `telethon` + `tgcrypto-pyrofork` only. |
| **Phase 1.5** | Wire-format fixes for `lskWebviewTokens` (QByteArray, not uint64), `lskBotStorages` (`Dict[PeerId, FileKey]` map, not single key), `lskPrefs 0x1E` (missed by every upstream fork — verified against TDesktop C++ source). |
| **Phase 2** | 2026 device fingerprints: iPhone 17 / Air, M5 / M5 Pro / M5 Max Macs, Galaxy S25 / S26 series, Pixel 10 / 10 Pro / 10 Pro XL, Android SDK 33-37 (Android 13 → 17 beta), macOS 26 Tahoe, iOS 26. Deterministic `_generate_tdesktop_app_version(unique_id)` for stable fingerprints across runs. |
| **Phase 3** | `kMaxAccounts = 6` (was 3, matches TDesktop's `kPremiumMaxAccounts`). `**kwargs` forward in `FromTelethon` → `QRLoginToNewClient` for `proxy`/`connection`/`timeout`. Nuitka-compatible `sharemethod`. Ruff lint replaces broken upstream pylint workflow. |
| **Phase 4** | 168 → 247 tests: QDataStream golden bytes, `hypothesis` property-based fuzzing (~1000 cases/run), real `TDesktop.SaveTData → load` roundtrip through `MapData.prepareToWrite()`. |
| **Phase 1.0.3** | **Security:** 6 DoS guards on attacker-controlled `count` fields in `MapData.read` / `_setMtpAuthorization.readKeys` / account-list. Pre-loop cap by `bytesAvailable() // pair_size` + hard regression tests (no fail-open xfail). |

## Install

### PyPI

```bash
pip install opentele-ng
```

```python
from opentele.td import TDesktop
from opentele.tl import TelegramClient
from opentele.api import API, CreateNewSession
```

**Runtime deps:** `telethon>=1.36,<2`, `tgcrypto-pyrofork>=1.2.7`. **No Qt.**

System libraries (`libgl1`, `libegl1`, `libxkbcommon-x11-0`, etc.) are **not**
required — you can deploy on Alpine, distroless, serverless, or any minimal
Linux container.

### Docker (v1.2.0+)

Multi-arch image at **`ghcr.io/stufently/opentele-ng`** (linux/amd64 + linux/arm64), ~140 MB, runs as non-root, `opentele-ng` is the entrypoint:

```bash
docker run --rm \
    -v "/path/to/Telegram/tdata:/tdata:ro" \
    ghcr.io/stufently/opentele-ng:latest info /tdata
```

See [`docs/examples/docker.md`](docs/examples/docker.md) for batch / convert / air-gapped / Sigstore verification.

## CLI — one-shot workflows (v1.1.0+)

```bash
# Read-only inspection of a tdata folder
opentele-ng info /path/to/Telegram/tdata

# Convert tdata → Telethon .session file
opentele-ng convert /path/to/Telegram/tdata --output ./me.session
```

See [`docs/examples/cli-quick-start.md`](docs/examples/cli-quick-start.md) for flags and exit codes.

## Quick start (Python API)

```python
import asyncio
from opentele.api import API, CreateNewSession
from opentele.td import TDesktop
from opentele.tl import TelegramClient

async def main() -> None:
    # 1. Load tdata produced by Telegram Desktop.
    tdata_path = r"C:\Users\<user>\AppData\Roaming\Telegram Desktop\tdata"
    tdesk = TDesktop(tdata_path)

    # 2. Pick an official API (TelegramIOS / TelegramAndroid / TelegramDesktop / TelegramMacOS).
    #    .Generate() builds a deterministic-or-random device fingerprint.
    api = API.TelegramIOS.Generate(unique_id="my-host")

    # 3. Convert TDesktop session → Telethon. CreateNewSession links a new
    #    device via QR code on the existing TDesktop session (no phone OTP).
    client: TelegramClient = await tdesk.ToTelethon(
        "new_session.session", CreateNewSession, api
    )

    async with client:
        await client.PrintSessions()

asyncio.run(main())
```

## Examples

- [`docs/examples/qr-login.md`](docs/examples/qr-login.md) — QR-code login flow
  with 2FA + `**kwargs` proxy forwarding.
- [`docs/examples/convert-tdata-to-telethon.md`](docs/examples/convert-tdata-to-telethon.md)
- [`docs/examples/convert-telethon-to-tdata.md`](docs/examples/convert-telethon-to-tdata.md)
- [`docs/examples/using-official-apis.md`](docs/examples/using-official-apis.md)

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `OPENTELE_EXTEND_STRICT` | `1` | `@extend_class` raises `TypeError` on attribute conflicts. Set to `0` to fall back to `RuntimeWarning` (legacy upstream behaviour). |
| `OPENTELE_REAL_TDATA_PATH` | unset | When set to an absolute path of a production tdata folder, enables the opt-in real-data smoke test in `tests/integration/test_real_tdata_smoke.py`. CI never sets it. |
| `OPENTELE_LENIENT_UNKNOWN_LSK` | unset (= strict) | Since 1.3.0. By default an unknown `lskType` in encrypted MapData raises `TDataReadMapDataFailed` (the unknown key's payload size is unknown, so reading on would desync the stream). Set to `1` to log a warning and stop parsing instead — you'll get a partial but consistent map. |

## Status

- Latest: **`v1.3.0`** (2026-05-20). PyPI: [`opentele-ng`](https://pypi.org/project/opentele-ng/) / Docker: [`ghcr.io/stufently/opentele-ng`](https://ghcr.io/stufently/opentele-ng) (Python 3.14). Production-ready. 1.3.0 closes 5 architectural known-issues from 1.2.2: **`kPerformanceMode` default flipped to `False`** so new tdata is actually encrypted (was using a hard-coded `localKey`), UTF-8 passcodes now work (was ASCII-only → crash), unknown `lskType` keys fail closed (was desyncing the stream), `StorageAccount` always reads/writes MTP config (was data-loss class in perf mode), and the Docker image now installs from a hash-locked deps file for reproducible builds.
- 295 tests pass on Python 3.10 / 3.11 / 3.12 / 3.13 / 3.14 (Docker matrix +
  GitHub Actions matrix × Ubuntu / macOS / Windows).
- Coverage: **~84% on the whole `opentele` package** (CI gate 80% on full package, was 90% on `opentele.td` only — that subset is still 94.83%).
- See [CHANGELOG.md](CHANGELOG.md) for the full per-release breakdown.

## Security

`opentele-ng` accepts attacker-influenced binary blobs (tdata files from the
filesystem), and version 1.0.3 added bounded-count guards on every loop that
reads a `count` field from a decrypted payload. If you find a malformed tdata
input that bypasses these guards or causes the library to read unbounded
memory or CPU, please report it privately: see [`SECURITY.md`](SECURITY.md).

## Differences from upstream

- **Import name unchanged** (`import opentele`) — drop-in for code that
  already uses `thedemons/opentele`.
- **PyPI dist name is `opentele-ng`** to avoid collision with the original
  package.
- **`kMaxAccounts`** is `6` (Telegram's premium limit), not 3.
- **`@extend_class`** raises on attribute conflicts by default; set
  `OPENTELE_EXTEND_STRICT=0` for the old warning-only behaviour.
- **`_settingsKey`** is `FileKey(0)` by default; the upstream
  `FileKey(1851671142505648812)` magic was removed in 1.0.1 (proper AES
  block padding added to `Storage.PrepareEncrypted` instead).
- **`PyQt6` is NOT a runtime dependency** — `opentele.td.qdatastream`
  provides byte-compatible pure-Python replacements for `QDataStream`,
  `QByteArray`, `QBuffer`, `QFile`, `QDir`, `QSysInfo`.

## Authorization

`opentele-ng` keeps the upstream's ability to use **official APIs** through
the `API` class (`API.TelegramDesktop`, `API.TelegramAndroid`,
`API.TelegramAndroidX`, `API.TelegramIOS`, `API.TelegramMacOS`,
`API.TelegramWeb_K`, `API.TelegramWeb_Z`).

Per [Telegram Terms of Service](https://core.telegram.org/api/obtaining_api_id#using-the-api-id):

> All accounts that sign up or log in using unofficial Telegram API clients
> are automatically put under observation to avoid violations of the Terms
> of Service.

Using an official API id/hash + `lang_pack="tdesktop"` (or `ios`, `android`,
etc.) makes the session indistinguishable from the corresponding official
client, which reduces spam-detection risk.

## Credits

See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md).

## License

MIT (same as upstream). See [LICENSE](LICENSE).

<p align="center">
<img src="https://raw.githubusercontent.com/thedemons/opentele/main/opentele.png" alt="logo" width="180"/>
</p>
