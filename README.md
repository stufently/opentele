<!-- vim: syntax=Markdown -->

# opentele-ng

**PyPI package name: [`opentele-ng`](https://pypi.org/project/opentele-ng/).**
This GitHub repository is called `opentele` for historical reasons; the package
it publishes is `opentele-ng`. Same project, two names.

```bash
pip install opentele-ng
```

The import path stays `opentele`, so existing code keeps working unchanged:

```python
from opentele.td import TDesktop
```

**What this fork changes:** `opentele-ng` is a maintained fork of
[thedemons/opentele](https://github.com/thedemons/opentele) that runs on
Python 3.10 – 3.14 and drops the PyQt5/PyQt6 runtime dependency entirely,
parsing tdata in pure Python. Upstream last released to PyPI in January 2022
and last committed in July 2024; it breaks on Python 3.13+ and pulls ~50 MB of
Qt wheels just to read binary streams.

[![PyPI version](https://img.shields.io/pypi/v/opentele-ng.svg)](https://pypi.org/project/opentele-ng/)
[![Python](https://img.shields.io/pypi/pyversions/opentele-ng.svg)](https://pypi.org/project/opentele-ng/)
[![CI](https://github.com/stufently/opentele/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/stufently/opentele/actions/workflows/ci.yml)
[![Lint](https://github.com/stufently/opentele/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/stufently/opentele/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/pypi/l/opentele-ng.svg)](LICENSE)
![No Qt](https://img.shields.io/badge/runtime-no%20Qt%20dependency-brightgreen)

## Why this fork

Upstream `thedemons/opentele` last shipped to PyPI in January 2022 (1.15.1) and
last committed in July 2024. By mid-2026 it stopped
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
| **Phase 6** | **Pyrogram bridge** (`ToPyrogram()` / `FromPyrogram()`, optional extra) — the "incoming feature" upstream never shipped; sends `lang_pack`, which Telethon cannot. **MTProto-layer-aware version picking**: the advertised Telegram Desktop version is drawn from builds that speak the same layer Telethon announces on the wire. 2026-10 Desktop table through 7.2.9 (layer 229); mobile/web fingerprints ( Android 12.9.0, iOS 12.9.2, Chrome 150 UA). |

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

**Runtime deps:** `telethon>=1.36,<2` on Python 3.10–3.13;
`telethon>=1.43,<2` on Python 3.14+ (synchronous client construction needs its
event-loop fix); `tgcrypto-pyrofork>=1.2.7`. **No Qt.** CI checks both the
minimum dependencies and the newest versions allowed by these ranges.

Optional Pyrogram bridge (`ToPyrogram()` / `FromPyrogram()`):

```bash
pip install "opentele-ng[pyrogram]"
```

Nothing Pyrogram-related is imported unless you call those methods, so the base
install stays two dependencies. The extra pulls `pyrofork`; vanilla `pyrogram`
and `kurigram` provide the same `pyrogram` import name and work too. See
[`docs/examples/pyrogram.md`](docs/examples/pyrogram.md).

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

- Latest: **`v1.4.2`** (2026-10-04). PyPI: [`opentele-ng`](https://pypi.org/project/opentele-ng/) / Docker: [`ghcr.io/stufently/opentele-ng`](https://ghcr.io/stufently/opentele-ng) (Python 3.14). Production-ready. 1.4.2 fixes CLI session replacement and disconnect flushing, raises the minimum Telethon to 1.43 on Python 3.14+, and refreshes CI actions with minimum-dependency checks. 1.4.1 ships the Telethon 1.45.0 / layer 229 alignment, refreshes the Docker lock, and adds official release checks to the monthly fork watch. 1.4.0 adds the **Pyrogram bridge** (`ToPyrogram()` / `FromPyrogram()`, optional `opentele-ng[pyrogram]` extra — the feature upstream listed as "incoming" for four years) and makes the advertised client version **MTProto-layer-aware**: `TELEGRAM_DESKTOP_LAYERS` maps each Telegram Desktop release to the layer read from its `api.tl`, and the version on the wire is picked to match the layer the installed Telethon (or Pyrogram) actually announces. Device/app fingerprints refreshed to July 2026. 1.3.2 fixes credential plumbing in `TelegramClient.__init__` — the plain Telethon-style positional call `TelegramClient(session, api_id, api_hash)` silently set `api_hash` to the `api_id`, so login RPCs failed with `ApiIdInvalidError` (`FromBundle` hit the same bug) — and makes the coverage gate measure the whole package instead of ~55% of it. 1.3.1 added `TelegramClient.FromBundle` (authorized client from a JSON bundle + session file) and fully automatic releases (version bump on `main` → tag → PyPI + GHCR via `autotag.yml`). 1.3.0 closed 5 architectural known-issues from 1.2.2: **`kPerformanceMode` default flipped to `False`** so new tdata is actually encrypted (was using a hard-coded `localKey`), UTF-8 passcodes now work (was ASCII-only → crash), unknown `lskType` keys fail closed (was desyncing the stream), `StorageAccount` always reads/writes MTP config (was data-loss class in perf mode), and the Docker image now installs from a hash-locked deps file for reproducible builds.
- 383 tests in the suite. Local Python 3.14 verification: **380 passed, 3
  opt-in tests skipped**, with **85.07% coverage** of the whole package
  (CI gate: 78%). CI covers Python 3.10–3.14 on Ubuntu, macOS and Windows;
  one test additionally skips below 3.13. Real-tdata tests require
  `OPENTELE_REAL_TDATA_PATH` and are not exercised in the default CI run.
- Monthly `Forks and releases watch` checks diverging forks, the latest stable
  Telegram Desktop's tagged MTProto layer, and Telethon against the Docker lock.
  Official release drift or a failed check produces a report even when forks
  have no activity. Run the release check locally with
  `python scripts/release_watch.py`; it needs no installed runtime dependencies.
- **tdata compatibility: checked against Telegram Desktop 7.2.9 source, with no
  version check in the way.** `Storage.ReadFile` validates the `TDF$` magic and
  the MD5 trailer, then reads the header's version field as information only
  (it becomes `TDesktop.AppVersion`); it is never compared against a floor or a
  ceiling, so nothing rejects a folder for being too new. Compatibility is
  decided by content instead. The `lskType` enum in `td/configs.py` matches
  TDesktop's own (`storage_account.cpp`) entry for entry, `0x00` – `0x1E`; the
  account-map reader dispatches `lskDraft` (`0x01`) through `lskPrefs`
  (`0x1E`), and an unrecognised key fails closed with a clear exception rather
  than desyncing the stream (see 1.3.0). `lskUserMap` (`0x00`) identifies the
  map file itself and is not written as a block by either side. Two naming and
  gating details worth knowing: `0x11` is still called `lskTrustedBots` here
  where TDesktop renamed it `lskTrustedPeers` (same ID), and the one hard
  equality in the MTProto path is `MTP.Config.kVersion == 1` — `DcOptions`
  accepts whatever positive version it finds on read and only writes
  `kVersion = 2`. Compared against the tagged v7.2.9 source (2026-09-17); the account-map
  layout, MTP.Config and DcOptions serialization remain unchanged from 7.0.9. A later release could still require work here if it adds a
  block type, changes the layout of an existing one, or bumps `MTP.Config`.
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
