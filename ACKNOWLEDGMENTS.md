# Acknowledgments

`opentele-ng` is a fork of [thedemons/opentele](https://github.com/thedemons/opentele),
released under MIT. The 11-phase modernization (May 2026) integrated work
from many sources — credit where credit is due.

## Upstream

- **[thedemons](https://github.com/thedemons)** — original `opentele`
  library (2022). All core architecture (`TDesktop`, `Account`, `MapData`,
  `Storage`, `MTProto auth`) is from upstream. Without it, this fork would
  not exist.

## Contributing forks (integrated patches)

The fork analysis surveyed 40+ active forks of upstream; the following
contributed actual patches or specific discoveries that landed in
`opentele-ng`:

### Phase 1 — Python 3.13/3.14 + PyQt6
- **[azamtoiri/opentele](https://github.com/azamtoiri/opentele)** — Python 3.13
  fix approach: `crossDelete` extension + `__func__`-based bound method
  comparison.
- **[iamlostshe/opentele](https://github.com/iamlostshe/opentele)** (deep fork
  via AlreadyNobody) — pointed to `tgcrypto-pyrofork` as replacement for
  abandoned `tgcrypto`.
- **[hustLer2k/opentele](https://github.com/hustLer2k/opentele)** (deep fork)
  — UTF-8 encoding for `setup.py` README read (Windows fix).
- **[Snowing](https://github.com/Snowing)** — `account.py:186` fix: invalid
  `map.stream >> legacyBackgroundKeyDay` (Python no-op) replaced with
  `readUInt64()`.

### Phase 1.5 — Wire-format fixes (verified against TDesktop C++)
- **[RobertAzovski/opentele](https://github.com/RobertAzovski/opentele)** —
  discovered 4 new `lskType` keys for Telegram Desktop 5.x-6.x tdata format:
  - `lskRoundPlaceholder` (0x1A) — single uint64
  - `lskInlineBotsDownloads` (0x1B) — single uint64
  - `lskMediaLastPlaybackPositions` (0x1C) — single uint64
  - `lskBotStorages` (0x1D) — corrected wire format to
    `Dict[PeerId, FileKey]` map after 3-AI code review (initial submission
    was a single uint64).
- `lskPrefs` (0x1E) — found by Codex during AI review by direct source dive
  into upstream Telegram Desktop C++ — not present in any community fork.

### Phase 2 — 2026 device fingerprints
- **[Paramon/opentele](https://github.com/Paramon/opentele)** — base for
  modern macOS device list + `_generate_tdesktop_app_version(unique_id)`.
- 2026 updates (Galaxy S26 series, M5 Mac lineup, iPhone 17 / Air, Android
  SDK 36/37) added during the Phase 2 work itself with verified sources.

### Phase 3 — Multi-account + QoL
- **[snakechilds/opentele-nuitka](https://github.com/snakechilds/opentele-nuitka)**
  — `kMaxAccounts` bump, `**kwargs` forwarding pattern in `FromTelethon`,
  Nuitka-friendly `sharemethod` rewrite.
- **[Ehekatech/opentele-tg](https://github.com/Ehekatech/opentele-tg)** —
  QR-login documentation skeleton.

## Telegram Desktop source

Wire format for the new `lskType` keys, `_settingsKey` AES alignment fix
(1.0.1), and DoS guard upper bounds (1.0.3) verified against upstream
**[telegramdesktop/tdesktop](https://github.com/telegramdesktop/tdesktop)**
`Telegram/SourceFiles/storage/storage_account.cpp` and
`storage_file_utilities.cpp` (dev branch).

## Code review

Every phase of `opentele-ng` was reviewed by **three independent AI systems**
running in parallel before push: **OpenAI Codex**, **Cursor**, and **Google
Gemini**. They caught critical issues that would otherwise have shipped:

- Phase 1.5: `lskWebviewTokens` was uint64×2 (wrong; should be QByteArray×2)
  — caught by all three AI; `lskBotStorages` was a single uint64 (wrong;
  should be a map) — Cursor + Codex; `lskPrefs` was completely missing —
  Codex via C++ source dive.
- Phase 2.5: `AndroidDevice.__gen__` was iterating the legacy 4500-model
  list against modern Android 13-17 SDKs (Galaxy S4 + Android 17 fingerprint)
  — all three; `macOSDevice.__gen__` `FromIdentifier` parser was corrupting
  clean model names (`"Mac16,9 (MacBook Air M4 13-inch)"` →
  `"MacMacBook Air Minch"`) — all three; macOS versions lost the `"macOS "`
  prefix — Codex.
- Phase 4: pure-Python `qdatastream` had no direct test coverage (tests used
  PyQt6 as oracle, never exercising the new code) — Codex; QString goldens
  missing — Gemini.
- Phase 1.0.2: untrusted `count` fields in `MapData.read` count loops were
  a real DoS vector — Codex's prediction confirmed by hand-built malformed
  payloads; this became the 1.0.3 release.
- Phase 1.0.3: a third count-loop in `tdesktop.py:__loadFromTData` was
  missed by the first pass — Codex + Gemini; the in-test `pytest.xfail()`
  fallback was a fail-open canary that needed to become a hard assert
  after the fix — all three.

## License

MIT (same as upstream). See [LICENSE](LICENSE).
