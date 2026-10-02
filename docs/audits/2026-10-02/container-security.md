# Container security and compatibility checks — 2026-10-02

The test image now runs as the existing production image's UID/GID 10001,
with a writable `/app` and `/home/app`. Package installation still happens
during the image build; the final pytest process runs without root. The two
invalid, abbreviated package-index sample tokens in `.env.example` are now
plain `replace-me` placeholders.

The first full test run found a pre-existing compatibility failure with newly
resolved Telethon 1.45.0: its MTProto layer is 229, while the newest Desktop
version in the table spoke layer 228. Running the same alignment tests as
root reproduced both failures. The table now also includes stable Desktop
7.2.9 and 7.2.8, whose official tagged schemas both specify layer 229:

- https://github.com/telegramdesktop/tdesktop/releases/tag/v7.2.9
- https://github.com/telegramdesktop/tdesktop/releases/tag/v7.2.8
- https://raw.githubusercontent.com/telegramdesktop/tdesktop/v7.2.9/Telegram/SourceFiles/mtproto/scheme/api.tl
- https://raw.githubusercontent.com/telegramdesktop/tdesktop/v7.2.8/Telegram/SourceFiles/mtproto/scheme/api.tl

The existing unknown-layer fallback expectation was updated to these newest
entries. No new tests were added. Existing Telegram API IDs and hashes were
not changed; the central scanner's ten findings for those public compatibility
templates remain visible for separate policy review.

## Local verification

- `docker build -f Dockerfile.test`: passed, final user `app`.
- Container runtime: UID/GID 10001; writes in `/app` and `/home/app` succeeded.
- Existing CI pytest command, excluding live `tests/tdata_test.py`:
  356 passed, 3 skipped; coverage 81.95%, above the 78% gate.
- `ruff check src/ tests/`: passed with the repository `.ruff.toml` mounted
  read-only, since the test image does not copy that file.
- Production `docker build`: passed. Its installed wheel retained
  `devices.json` and `py.typed`, imported without Qt, ran with UID 10001,
  and matched the hash-locked Telethon runtime's layer 227.
- Production CLI `--help`: passed.
- `git diff --check`: passed.

These are build, runtime and existing test results, not a new native security
scan or hosted CI result. No real Telegram login, provider request, deployment
or external notification was performed.
