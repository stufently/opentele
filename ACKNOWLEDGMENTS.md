# Acknowledgments

`opentele-ng` — fork of [thedemons/opentele](https://github.com/thedemons/opentele), released under MIT.

## Upstream

- **[thedemons](https://github.com/thedemons)** — original `opentele` library (2022). All core architecture (`TDesktop`, `Account`, `MapData`, `Storage`, `MTProto auth`) is from upstream. Without it, this fork would not exist.

## Contributing forks (integrated patches)

Phase 1 & 1.5 of `opentele-ng` integrates fixes from multiple community forks:

- **[RobertAzovski/opentele](https://github.com/RobertAzovski/opentele)** — discovered 4 new `lskType` keys for Telegram Desktop 5.x-6.x tdata format:
  - `lskRoundPlaceholder` (0x1A)
  - `lskInlineBotsDownloads` (0x1B)
  - `lskMediaLastPlaybackPositions` (0x1C)
  - `lskBotStorages` (0x1D) — note: Phase 1.5 corrected wire format to map `Dict[PeerId, FileKey]` after AI code review (initial implementation was single uint64)
- **[azamtoiri/opentele](https://github.com/azamtoiri/opentele)** — Python 3.13 fix approach: `crossDelete` extension + `__func__`-based bound method comparison.
- **[Snowing](https://github.com/Snowing)** — `account.py:186` fix: invalid `map.stream >> legacyBackgroundKeyDay` (Python no-op) replaced with `readUInt64()`.
- **[iamlostshe/opentele](https://github.com/iamlostshe/opentele)** (deep fork via AlreadyNobody) — pointed to `tgcrypto-pyrofork` as replacement for abandoned `tgcrypto`.
- **[hustLer2k/opentele](https://github.com/hustLer2k/opentele)** (deep fork) — UTF-8 encoding for `setup.py` README read (Windows fix).

## Telegram Desktop source

Wire format for new `lskType` keys verified against upstream **[telegramdesktop/tdesktop](https://github.com/telegramdesktop/tdesktop)** `Telegram/SourceFiles/storage/storage_account.cpp` (dev branch). This included discovery of `lskPrefs` (0x1E), missed by all forks.

## Review

Phase 1 & 1.5 code reviews were performed by three independent AI systems:
- OpenAI Codex — found `lskPrefs` and verified wire formats against C++ source
- Cursor — identified `lskWebviewTokens` and `lskBotStorages` format mismatches
- Google Gemini — confirmed `__func__` comparison and PyQt6 enum migration

## License

MIT (same as upstream). See [LICENSE](LICENSE).
