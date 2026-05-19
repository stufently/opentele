# Changelog
All notable changes to this project will be documented in this file.

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
- `src/td/account.py` `lskWebviewTokens` — conflict-resolution артефакт (`is_finished = True` вместо чтения двух uint64) теперь корректно читает `webviewStorageTokenBots` и `webviewStorageTokenOther` парой `readUInt64()`. До фикса любой ключ после `lskWebviewTokens` в tdata игнорировался.

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