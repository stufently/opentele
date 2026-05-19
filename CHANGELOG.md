# Changelog
All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-05-19 — opentele-ng Phase 3 (multi-account + kwargs + nuitka + QR docs + linter)

Phase 3 picks up the QoL fixes from `snakechilds/opentele-nuitka` and `Ehekatech/opentele-tg`, plus replaces the broken upstream pylint workflow with ruff. The 3-AI prep review (Codex) corrected scope before implementation:
- `kMaxAccounts` → 6 (TDesktop's premium account limit), not 100 (snakechilds' value makes no sense — Telegram Desktop itself caps at 6).
- Unknown `lskType` fail-fast deferred to Phase 4 — current `logging.warning` already desyncs the stream; switching to `raise` without first knowing payload size for unknown keys is risky.

### Added
- **`TDesktop.kMaxAccounts = 6`** — was hardcoded 3 in upstream. Matches Telegram Desktop's `kPremiumMaxAccounts` from `main_domain.h`. Real-world Premium users can now load all 6 accounts from a single tdata folder.
- **`**kwargs` forwarding** in `TDesktop.FromTelethon` and `Account.FromTelethon` — Telethon-specific options (proxy, connection, timeout) now flow through to `QRLoginToNewClient` without bridge-layer modification. Source: snakechilds/opentele-nuitka commit `073329c`, adapted with `**kwargs` rather than `kwargs: dict = None`.
- **`docs/examples/qr-login.md`** (+115 lines) — full QR-code login example: minimal flow, 2FA branch, tdata conversion, kwargs forwarding for proxy/connection. Source: Ehekatech/opentele-tg commit `c7550ba`, expanded with Phase 3 context.
- **Ruff workflow** (`.github/workflows/lint.yml`) — replaces broken upstream `pylint.yml` (Python 3.7, EOL). Runs `ruff check src/ tests/` on push/PR.
- **`.ruff.toml`** with conservative rule set tailored to upstream code style (ignores `E711`, `E731`, `W293`, `F401`, etc. — patterns we don't want to mass-rewrite). Strict on new code added in Phase 1+.
- **6 new Phase 3 tests** (`tests/test_phase3_features.py`) covering kMaxAccounts, kwargs forwarding, sharemethod nuitka fix, QR docs existence.
- Total: 92 → 98 tests, all green on Python 3.10–3.14 Docker matrix.

### Changed
- **`utils.sharemethod.__new__`** — `clsName = func.__class__.__name__`, `bases = func.__class__.__bases__`, `attrs = func.__dict__` → stable literals `"function"`, `(object,)`, `{}`. The dynamic form broke Nuitka compilation (snakechilds `eb4ff4d`). Runtime behavior unchanged — the synthetic class name/bases don't matter, the descriptor wraps the function regardless.
- **MaxAccountLimit error message** now interpolates current `kMaxAccounts` (was hardcoded `"more than 3"`).
- **Imports across 30 files** auto-sorted by ruff (cosmetic, no behavior change).
- Removed `.github/workflows/pylint.yml` (upstream, broken: targets Python 3.7 which is EOL on GitHub-hosted runners).

### Process
- 3-AI prep review (Codex / Cursor / Gemini) before Phase 3 implementation; Codex caught the `kMaxAccounts=100` and unknown-keyType scope issues. Gemini hit rate limit, Cursor failed twice in this batch (network) — Codex review carried the gate.
- Linter integrated into Docker test image + CI; ruff `check` enforced, format not enforced (preserves upstream code as-is).

## [0.2.1] - 2026-05-19 — opentele-ng Phase 2.5 (fingerprint review fixes)

Three independent AI code reviews (Codex, Cursor, Gemini) on `v0.2.0-phase2` flagged 4 critical and several high/medium issues. Phase 2 added device lists but the `__gen__()` methods didn't actually use them — `RandomDevice()` produced legacy 2017-2022 phones paired with Android 16 SDK. Phase 2.5 fixes the runtime generation layer.

### Fixed (critical)
- **`macOSDevice.system_versions`** — restored `"macOS X.Y"` prefix (Phase 2 init stripped it, producing bare `"26.0"`). TDesktop `SystemVersionPretty()` returns prefixed form; without it, fingerprint regressed below Phase 1.5 quality.
- **`macOSDevice.__gen__`** — `FromIdentifier` parser stripped digits/punctuation from new clean-name strings, collapsing `"Mac16,9 (MacBook Air M4 13-inch)"` → `"MacMacBook Air Minch"`. Now applies only to legacy board IDs (`"MacBookPro16,4"` style); clean names pass through.
- **`AndroidDevice.__gen__`** — was iterating legacy 4500-model list × SDK 33-37 (unrealistic: 2017 Redmi + Android 17). Now uses `device_models_by_sdk` pairing (modern flagships only). Legacy `device_models` retained as fallback for unforeseen consumers.
- **Mac M5 identifiers**: dropped guessed `Mac17,3 (M5 base)` / `MacBookPro18,3-5 (M5 series)` — instead store clean marketing names (`"MacBook Pro 14-inch M5 Max"`) since TDesktop `initConnection.device_model` sends marketing strings, not board IDs.

### Fixed (high)
- **Galaxy S26 SM codes**: removed duplicate `SM-S931` shared with S25 base. S26 series now `SM-S941` (base), `SM-S946` (+), `SM-S948` (Ultra) — consistent with Samsung's `SM-S9X1/X6/X8` series naming.
- **`API.TelegramAndroid.device_model`**: unified with `device_models_modern` — was `"Samsung SM-S938"` (raw SKU), now `"Samsung Galaxy S25 Ultra (SM-S938)"` (matches marketing+SKU pattern Telegram Android sends).

### Fixed (medium)
- **`API.TelegramAndroidX.app_version`** — `12.6.0 (6500)` was Android-mainline format; Telegram X (TGX) uses distinct pattern `0.X.Y.Z-arm64-v8a`. Now `"0.27.5.1842-arm64-v8a"`. Source: Paramon `c0d8085`.
- **`API.TelegramMacOS`** — `8.4 / macOS 12.0.1 / MacBook Pro` (2022 stale) → `11.13 / macOS 26.0 / MacBook Pro 14-inch M5`.
- **Intel Macs added** to `macOSDevice.device_models` for backward fingerprint diversity (iMac Pro, iMac Retina 5K 27 2020, Mac mini 2018, MBP 16 2019, MBP 13 2020) — Apple's compatibility list for macOS Tahoe.

### Added (tests)
- **12 new runtime tests** in `tests/test_devices_runtime.py` covering actual `RandomDevice()` and `API.*.Generate()` output (not just static list contents):
  - `test_macOSDevice_random_model_has_no_FromIdentifier_corruption` (catches `"Minch"`, `"MacMac"`)
  - `test_AndroidDevice_random_uses_modern_devices_not_legacy_4500_list`
  - `test_macOSDevice_system_versions_have_macOS_prefix`
  - `test_telegram_desktop_macos_generate_returns_macos_prefix`
  - `test_AndroidDevice_random_system_version_is_modern_sdk` (SDK ≥ 33)
  - plus iOS / Windows runtime smoke
- Total: 79 → 91 tests, all green on Python 3.10–3.14 (Docker matrix).

### Review process
- Round 1 review: Codex (verified C++ via `gist.githubusercontent.com/adamawolf/3048717` + Apple Support), Cursor (deep diff against `__gen__`), Gemini (FromIdentifier failure mode analysis). All three agreed: do not push Phase 2 as-is.

## [0.2.0] - 2026-05-19 — opentele-ng Phase 2 (2026 device fingerprints)

Phase 2 brings device/OS/app-version fingerprints up to **May 2026**: 7 months past Paramon's 2025-10 baseline, 4 years past upstream `thedemons/opentele` (2022).

### Added
- **`API.TelegramDesktop._generate_tdesktop_app_version(unique_id=None)`** — random or deterministic (sha1-based by `unique_id`) Telegram Desktop version picker. Source list `TELEGRAM_DESKTOP_VERSIONS` covers v5.16.0 (Jul 2025) through v6.8.2 (May 2026), ~55 versions. Source: Paramon/opentele patterns (`de639ac` + `41f3ea5`), adapted with 2026 release data.
- `iOSDevice` proper class name; `iOSDeivce` kept as alias for backward compat (upstream typo).
- `AndroidDevice.device_models_by_sdk` — Dict[str, List[str]] mapping SDK 33-37 to realistic devices supporting that Android version (Ehekatech pattern).
- 25 new tests covering modern device fingerprints + version generation (`test_devices_modern.py`, `test_api_app_versions.py`).

### Changed
- **macOS**: dropped 10.x–13.x (EOL). Now: 14.x Sonoma, 15.x Sequoia, **26.x Tahoe** (Sept 2025+).
- **macOS devices**: dropped pre-M1 Intel Macs (no macOS 14+ support). Added M2, M3, M4, **M5/M5 Pro/M5 Max** (Oct 2025 / Mar 2026), MacBook Air M5 (Spring 2026).
- **iOS**: dropped 12-17 (legacy). Now: **iOS 18** (Apple Intelligence, Sep 2024+) and **iOS 26** (Liquid Glass redesign, Sep 2025+, Apple skipped 19-25 numbering).
- **iOS devices**: dropped iPhone 11 and below. Added **iPhone 17 / 17 Pro / 17 Pro Max / iPhone Air** (Sep 2025), iPhone 16/16e (Sep 2024), 15 series; kept 14 / 13 Pro Max / SE 3rd gen for compatibility.
- **Android SDK**: dropped SDK 23-32 (Android 6-12). Now: SDK 33-37 (Android 13 → Android 17 beta).
- **Android devices**: added 2024-2026 flagships — **Galaxy S25 series + S25 Edge + S25 FE** (Jan-Sep 2025), **Galaxy S26 series** (Mar 11, 2026), **Pixel 10 / Pro / Pro XL** (Aug 2025), **OnePlus 12/13**, **Xiaomi 14 Pro / 15 / 15 Pro**.
- **Windows**: dropped 7/8/8.1 (EOL). Now: Windows 11, Windows 10.
- **`API.TelegramDesktop.app_version`**: `3.4.3 x64` → `6.8.2 x64`.
- **`API.TelegramAndroid.app_version`**: `8.4.1 (2522)` → `12.6.0 (6500)`; `device_model`: `Samsung SM-G998B` (S21) → `Samsung SM-S938` (S25 Ultra); `system_version`: `SDK 31` → `SDK 36`.
- **`API.TelegramAndroidX.app_version`**: same modern Galaxy S25 fingerprint.
- **`API.TelegramIOS.app_version`**: `8.4` → `12.7`; `device_model`: `iPhone 13 Pro Max` → `iPhone 17 Pro Max`; `system_version`: `14.8.1` → `26.0`.
- `TelegramDesktop.Generate(unique_id=...)` now produces random/deterministic `app_version` from the v5.16-v6.8 list, not the hardcoded default.

### Sources
- Paramon/opentele commits: `2fb902c`, `1cf069a`, `c0d8085`, `6e69836`, `41f3ea5`, `de639ac`
- Telegram Desktop releases: `github.com/telegramdesktop/tdesktop/releases` (v5.16.0 → v6.8.2)
- Apple device identifiers: `gist.github.com/adamawolf/3048717` (iPhone18,1–iPhone18,4 confirmed)
- Apple M5 / M5 Pro / M5 Max: Wikipedia (Oct 2025 / Mar 2026)
- Samsung Galaxy S26: Wikipedia (Mar 11, 2026; Android 16 / OneUI 8.5)
- Android API levels: `apilevels.com` (SDK 36 = Android 16 stable, SDK 37 = Android 17 beta)

## [0.1.1] - 2026-05-19 — opentele-ng Phase 1.5 (review fixes)

After three independent AI code reviews (Codex, Cursor, Gemini), Phase 1's "fresh tdata read" implementation had wire format mismatches with upstream Telegram Desktop `storage_account.cpp`. Phase 1.5 fixes them.

### Fixed (critical)
- **`lskWebviewTokens` (0x19)**: was read/written as two `uint64`; upstream TDesktop is **two `QByteArray`** (token data, not file keys). Phase 1.5 uses `stream >> QByteArray` and `td.Serialize.bytearraySize()` for size accounting. Without this fix, any tdata with non-empty webview tokens would desync the stream.
- **`lskBotStorages` (0x1D)**: was read/written as single `uint64`; upstream TDesktop is **map**: `uint32 count + count × (uint64 FileKey, uint64 PeerId)`. Phase 1.5 uses `Dict[PeerId, FileKey]` (analogous to `_draftsMap`). Without this fix, all bot-storage entries were silently dropped + offset shift propagated to subsequent keys.

### Added
- **`lskPrefs` (0x1E)**: missed by Phase 1 init. Wire format: `uint64 prefsKey` (like `lskLocations`). Without this key, any tdata with `_prefsKey` set would hit the `else: logging.warning(...)` branch and desync.
- Full MapData stream roundtrip test (`tests/test_account_mapdata_full_roundtrip.py`) — writes and reads 5 new keys consecutively, verifies stream ends cleanly (`stream.atEnd() && status == Ok`).
- `tests/test_account_lskWebviewTokens_wire_format.py`, `tests/test_account_lskBotStorages_wire_format.py`, `tests/test_account_lskPrefs.py` — per-key wire format guards.
- `tests/test_dependencies_smoke.py` — `tgcrypto-pyrofork` AES-IGE roundtrip on 16/32/64/128/256 byte payloads + telethon version assertion.
- `tests/test_utils_extend_class_strict.py` — strict-mode / soft-mode coverage.
- `tests/test_utils_extend_class_validation.py` — `@extend_class` rejects non-classes with `TypeError`.
- `ACKNOWLEDGMENTS.md` — credits to upstream and contributing forks.
- `OPENTELE_EXTEND_STRICT=0` env flag — switches `@extend_class` to soft mode (RuntimeWarning); default is strict (TypeError on conflicts).

### Changed
- `@extend_class` now **strict by default**: real attribute conflicts (not PEP 749 dunders) raise `TypeError`, not `RuntimeWarning`. Use `OPENTELE_EXTEND_STRICT=0` for the old behavior.
- `@extend_class` validates `decorated_cls` (not `cls`), since `cls` is always the metaclass `type`.
- `requirements.txt`: pinned `telethon<2` upper bound until Telethon 2.x compatibility is verified.
- README: marked Python 3.14 support as experimental (3.14 itself is still in active development as of 2026-05).
- setup.py description and keywords aligned with corrected lskType semantics.

### Total
44 → 52 tests, all green on Python 3.10/3.11/3.12/3.13/3.14 (Docker matrix).

## [0.1.0] - 2026-05-19 — opentele-ng Phase 1

### Added
- Python 3.13 / 3.14 support: расширен `crossDelete` в `extend_class` для новых dunder-атрибутов из PEP 749 (`__firstlineno__`, `__static_attributes__`); добавлено `__func__`-based сравнение bound methods (закрывает edge-case с меняющимся `id()`); fail-soft (warning вместо `raise BaseException`) на конфликт атрибутов. (источник: azamtoiri)
- 4 новых `lskType` для tdata формата Telegram Desktop 5.x – 6.x: `lskRoundPlaceholder` (0x1A), `lskInlineBotsDownloads` (0x1B), `lskMediaLastPlaybackPositions` (0x1C), `lskBotStorages` (0x1D) — чтение и запись. (источник: RobertAzovski)
- Docker-based test harness (`Dockerfile.test`) и pytest smoke suite (`tests/test_imports.py`, `test_utils_extend_class.py`, `test_configs_lskType.py`, `test_account_*.py`).
- GitHub Actions CI matrix: Python 3.10/3.11/3.12/3.13 × Ubuntu/macOS/Windows + Python 3.14 на Ubuntu.

### Changed
- Зависимости: `PyQt5` → `PyQt6 >= 6.6`.
- Зависимости: `tgcrypto` → `tgcrypto-pyrofork >= 1.2.7` (tgcrypto заброшен с 2022).
- `telethon >= 1.36` минимум.
- Имя пакета на PyPI: **`opentele-ng`**. Import name остаётся `opentele` для backward compatibility.
- `setup.py`: UTF-8 encoding при чтении `README.md` (фикс для Windows). `python_requires=">=3.10"`.

### Fixed
- `src/td/account.py:186` — невалидный Python `map.stream >> legacyBackgroundKeyDay` в обработке `lskBackgroundOldOld` заменён на корректный `legacyBackgroundKeyDay = map.stream.readUInt64()`. (источник: Snowing)
- `src/td/account.py` `lskWebviewTokens` — conflict-resolution артефакт (`is_finished = True` вместо чтения данных) теперь корректно читает `webviewStorageTokenBots` и `webviewStorageTokenOther`. До фикса любой ключ после `lskWebviewTokens` в tdata игнорировался. **Note:** в Phase 1 init wire format был ошибочно реализован как два `readUInt64()` — это исправлено в Phase 1.5 (v0.1.1) на два `QByteArray` после сверки с TDesktop C++ source.

## [v1.15](https://pypi.org/project/opentele/1.15/) - 2022-01-27

- Massive performance upgrade, UseCurrentSession is now 200x faster than before.
- `TDesktop` now has `PerformanceMode` which is enabled by default. It will now load and save tdata 200x faster.
- Huge performance boost when converting `TelegramClient` to `TDesktop`.
- Replace `inspect.stack()` with `inspect.currentframe()` in `OpenTeleException`. Using `inspect.stack()` is a stupid move, it's really slow.

## [v1.14](https://pypi.org/project/opentele/1.14/) - 2022-01-26

- `TelegramClient` will now use `TelegramDesktop` api by default.
- Fix a bug when saving tdata.

## [v1.13](https://pypi.org/project/opentele/1.13/) - 2022-01-21

- Fix `unique_id` not generated correctly in `API.Generate()`
- Added DC mismatched handling when authorizing a new client.

## [First Stable Release](https://pypi.org/project/opentele/1.13/) - 2022-01-20

- First stable release of opentele.