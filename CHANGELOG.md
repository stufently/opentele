# Changelog
All notable changes to this project will be documented in this file.

## [Unreleased]

## [1.2.2] - 2026-05-20 — Devices JSON refactor + CodeQL findings + GH labels + CI hardening

### Known issues (filed for follow-up release)

Surfaced by the project-wide 3-AI review during 1.2.2. None are runtime regressions vs 1.2.1, but they should be addressed in a follow-up release:

1. **`kPerformanceMode = True` is the default**, which means new tdata created via `TDesktop.SaveTData(path)` (no passcode) is encrypted with a hard-coded `localKey` — i.e. effectively unencrypted. This is upstream behaviour, but should be opt-in rather than default. Flip default in 1.3.0 + deprecation warning.
2. **Non-ASCII local passcodes crash** with `UnicodeEncodeError` instead of a domain `OpenTeleException` (`src/td/tdesktop.py:130/200/265` encode as ASCII). Cyrillic/emoji passcodes unsupported.
3. **`StorageAccount.start()` skips reading `config` when in performance mode** (`src/td/account.py:631`), which means certain MTP config fields are lost on re-save. Performance toggle should not change data semantics.
4. **Unknown `lskType` keys** are logged but their payload is not skipped (`src/td/account.py:329`), so a future TDesktop with a new lskType will desync the read cursor. Need either fail-fast strict mode or generic length-skip.
5. **Docker runtime deps not lock-hashed.** `telethon>=1.36,<2` + `tgcrypto-pyrofork>=1.2.7` resolve fresh at image build. Reproducible image needs a constraints lock file.

### Fixed

### Fixed
- **`src/devices.py:5333` — data bug from upstream**: `"Huawei MediaPad 7 Vogue" "Huawei LEO-BX9",` (missing comma) was being silently concatenated by Python into a single bogus device name `"Huawei MediaPad 7 VogueHuawei LEO-BX9"` — and the real `LEO-BX9` was missing from the device fingerprint list. CodeQL warning `py/implicit-string-concatenation-in-list` caught it. The Android device list now has 4870 entries (was 4869).
- **`tests/qdatastream/test_pure_errors.py:514` — `py/side-effect-in-assert`**: `assert f.open(Mode.ReadOnly) is True` is invalid under `python -O` (asserts stripped → file never opens, test silently passes). Split into `opened = f.open(...); assert opened is True`. CodeQL ERROR closed.
- **`src/__main__.py:39, 125` — `py/empty-except`**: added explanatory comments so reviewers / CodeQL see the intent (best-effort diagnostic / cleanup paths).

### Changed
- **`src/devices.py`: 174 KB → 17 KB** (-90%). The four huge `device_models` lists (Desktop 790, macOS 37, Android 4870, iOS 20) moved to `src/devices.json`, loaded once on import via `_load_devices_json()`. Class-level `device_models: List[str] = _DATA["..."]["device_models"]` line replaces ~5700 lines of Python list literals. `system_versions` lists stay inline — they're tiny and carry valuable per-version comments.
- **`pyproject.toml`** + **`MANIFEST.in`**: ship `src/devices.json` as package data so wheel users get it.

### Added
- **`scripts/extract_devices_data.py`** — one-shot extractor: reads the in-memory class attributes and writes `src/devices.json`. Re-run when device lists change. Idempotent.
- **`scripts/slim_devices_py.py`** — one-shot rewriter: replaces literal `device_models = [...]` blocks in `devices.py` with JSON-backed references. Idempotent (no-op if already migrated).
- **Repository labels created** via `gh label create`: `wire-format`, `forks-watch`, `dependencies`, `python`, `ci`, `docker`, `security`. Issue templates that reference them now actually attach the labels on submit (Cursor + Codex catch from 1.2.0 review).

### Verified
- 270 tests pass on Python 3.10–3.14, coverage 83.55% on the whole package.
- **Regression sentinel on 2 real Telegram Desktop tdata folders** (TD 6.0.6 + TD 6.0.8) under `/home/deploy/autootvetchik/opentelettesttdata/`: `authKey_sha256` matches the stored values byte-for-byte (`544e4b3edf450a18…` for tdatanew, `775161c1b987143b…` for Telegram_27637711346). Zero wire-format regression from the JSON refactor.
- `docker pull ghcr.io/stufently/opentele-ng:1.2.2 && docker run --rm … info /tdata` works on both fixtures with `mainAccount_index = 0`.

## [1.2.1] - 2026-05-20 — Coverage scope, QFile.bytesAvailable, Py3.14 Docker, cleanup

### Changed
- **Docker base image switched to `python:3.14-slim`** (was `3.13-slim`), digest-pinned to `sha256:a7185a8e…` for reproducibility. The PyPI wheel is still pure-Python and works on Python 3.10–3.14 — the change only affects the GHCR container. `scripts/publish.sh` and `Dockerfile.test` follow the same Py3.14 bump.
- **Coverage gate scope expanded from `--cov=opentele.td` to `--cov=opentele`**. Gates the WHOLE package, surfacing previously-invisible gaps in `__main__.py` (CLI), `tl/telethon.py`, `api.py`. Threshold lowered to 80% (was 90% on `.td` only) to accommodate `tl/telethon.py`'s 24%-covered QR-login paths that need a live Telegram socket to exercise. The `opentele.td` package itself stays at 94.83%.

### Added
- **`QFile.bytesAvailable()`** in `src/td/qdatastream.py` — mirrors `QIODevice` contract so `QDataStream` over a `QFile` behaves identically to one over a `QBuffer`. Today's `storage.py` hot path reads files into a `QByteArray` before parsing, so this is consistency hardening rather than a hot-path bug fix — but `_GuardCount` in `account.py` calls `stream.bytesAvailable()`, so any future caller that streams `MapData` from a `QFile` directly would have hit a spurious `TDataReadMapDataFailed`. Caught by Gemini in the 1.2.0 review, deferred to here. **4 new tests** in `tests/qdatastream/test_pure_errors.py`.
- **CLI integration tests on a real fixture tdata** — `test_cli_info_on_real_fixture_tdata_succeeds` and `test_cli_info_json_on_real_fixture_tdata_parses` build a tdata via `TDesktop.SaveTData()` and invoke `python -m opentele info` as a subprocess. These are the tests that would have caught the 1.1.0 Windows regressions (`types.auth` shadowing and the `MainAccount`→`mainAccount` typo) before they reached users.

### Removed
- `docs/build/` (72 KB) and `docs/documentation/` (256 KB) — stale upstream documentation that was already excluded from the mkdocs site via `exclude_docs`. Cleaned up the matching exclude entries in `mkdocs.yml`.

### Verified
- 270 tests pass on Python 3.10–3.14 (was 264; +6 from QFile.bytesAvailable, +2 from CLI fixture tests). Coverage 83.48% on the whole `opentele` package; `opentele.td` subset still at 94.83%.
- `docker build -t opentele-ng:py314 .` on the new base + smoke `info` on real tdata works end-to-end on Python 3.14.5.

## [1.2.0] - 2026-05-20 — Docker image + supply-chain hardening + forks watch

### Fixed (Windows regressions reported on 1.1.0)
- **`opentele-ng info` crashed on Windows consoles (cp1251 / cp437)** with `UnicodeEncodeError` on the `└─` box-drawing character. `_ensure_utf8_stdout()` now reconfigures `sys.stdout` / `sys.stderr` to UTF-8 at CLI startup (safely no-ops on streams without `reconfigure`, e.g. `io.StringIO` under pytest).
- **`opentele-ng convert` (default `CreateNewSession` mode) crashed with `AttributeError: module 'types' has no attribute 'auth'`** during QR-login. `src/tl/telethon.py` now imports `telethon.types` explicitly — previously it relied on `from .configs import *` which in some environments was shadowed by the stdlib `types` module (e.g. when `src/exception.py` ran `import types` earlier in the import order). Added 2 regression tests in `tests/test_cli.py`.

### Added
- **Docker image** at `ghcr.io/stufently/opentele-ng` — multi-arch (linux/amd64 + linux/arm64), ~140 MB, non-root user, `opentele-ng` as entrypoint. Tags: `:latest`, `:1.2.0`, `:1.2`, `:1`, `:main`, `:sha-<7>`. Built + pushed by `.github/workflows/docker.yml` on every push to `main` and on every `v*` tag.
- **`docs/examples/docker.md`** — full Docker usage guide (info, convert, batch, air-gapped, Sigstore verification).
- **PEP 740 attestations** on PyPI uploads — `pypa/gh-action-pypi-publish` configured with `attestations: true`. Combined with Trusted Publishing this gives end-to-end signed provenance from GitHub commit → wheel on PyPI.
- **Build provenance + SBOM on the Docker image** — `docker/build-push-action` runs with `provenance: true` + `sbom: true`, plus `actions/attest-build-provenance` for the OCI registry. Verifiable via `gh attestation verify oci://ghcr.io/stufently/opentele-ng:1.2.0 --repo stufently/opentele`.
- **`.github/dependabot.yml`** — weekly PRs for pip / GitHub Actions / Docker base image updates.
- **`.github/workflows/codeql.yml`** — CodeQL static analysis on push, PR, and weekly schedule.
- **`.github/ISSUE_TEMPLATE/`** + **`.github/pull_request_template.md`** — structured forms for bug reports, wire-format mismatches, feature requests, and PR submissions.
- **`.pre-commit-config.yaml`** — ruff + check-yaml + detect-private-key. `pre-commit install` once → ruff/CI surprises stop. Pinned to `ruff 0.15.13` to match CI.
- **`.github/workflows/forks-watch.yml`** + **`scripts/fork_watch.py`** — monthly (1st of month, 12:00 UTC) scan of public forks of `thedemons/opentele` for new commits. Generates a Markdown report and **opens it as a GitHub Issue** (label `forks-watch`) so it lands in the maintainer's notifications. No secrets — uses the default `GITHUB_TOKEN`.

### Verified
- `docker build -t opentele-ng:dev . && docker run --rm opentele-ng:dev info /tdata` works end-to-end on a real Telegram Desktop tdata (TD 6.0.6). `mainAccount_index` reads correctly (regression catch from 1.1.0).
- Manual run of `python scripts/fork_watch.py` returns a clean Markdown report against the current public fork graph (1 fork with activity in last 35 days).
- 262 tests pass on Python 3.10–3.14, coverage 94.83% on `opentele.td` (unchanged).

## [1.1.0] - 2026-05-20 — CLI, pyproject.toml, Trusted Publishing, docs site

First minor bump since 1.0.0. Major theme: bring the project up to modern Python packaging standards (PEP 621 pyproject, PEP 561 typing marker, Trusted Publishing) and ship a native CLI so the 80% conversion case no longer requires hand-rolled Python.

### Added
- **`opentele-ng` CLI** (entry point `opentele.__main__:main`):
    - `opentele-ng info <tdata>` — read-only summary of accounts (UserId, DcId, AppVersion, sha256 of authKey). `--json` for machine-readable output.
    - `opentele-ng convert <tdata> -o <session>` — convert tdata to a Telethon `.session` file. `--use-current-session` to reuse rather than create a new session; `--force` to overwrite.
    - `opentele-ng --version`, `opentele-ng --help`.
    - 8 new tests in `tests/test_cli.py` (argparse, exit codes, refuse-overwrite, info/convert path validation).
- **PEP 561 typed marker** (`src/py.typed`) — IDEs and type-checkers (mypy, pyright) now pick up our type annotations. Classifier `Typing :: Typed` re-introduced.
- **`opentele.__version__`** — read from `importlib.metadata`. Fallback `0.0.0+unknown` for editable installs without metadata.
- **`CONTRIBUTING.md`** + **`CODE_OF_CONDUCT.md`** (Contributor Covenant 2.1).
- **`BENCHMARKS.md`** + `scripts/benchmark.py` — pure-Python `QDataStream` measured against PyQt6 baseline. Pure-Python is 1.5–4× slower on micro-ops (which is negligible inside a real tdata load — disk + AES dominate).
- **`docs/examples/cli-quick-start.md`** + **`docs/examples/batch-convert.md`** — two new examples covering the CLI and parallel batch conversion.
- **`mkdocs.yml`** + **`docs/index.md`** — minimal Material-themed docs site (replaces upstream's stale Read the Docs config).
- **`.github/workflows/publish.yml`** — automated PyPI publish via [Trusted Publishing (OIDC)](https://docs.pypi.org/trusted-publishers/) on `v*` tags. No long-lived API token in the repo.
- **`.github/workflows/docs.yml`** — auto-build + deploy mkdocs to GitHub Pages on `main`.

### Changed
- **`setup.py` removed.** All metadata lives in `pyproject.toml` (PEP 621). Build backend is `setuptools.build_meta`, same as before.
- **`requirements.txt`** still present for `pip install -r requirements.txt`-style dev workflows, but pyproject.toml is the single source of truth for runtime deps. Test deps moved into `[project.optional-dependencies] test = [...]` — install with `pip install -e '.[test]'`.
- **README badges** switched from hardcoded counts to live PyPI / GitHub Actions badges (`pypi/v`, `pypi/pyversions`, `pypi/l`, CI/Lint workflow badges).

### Verified
- 262 tests pass (was 252) on Python 3.10–3.14. Coverage 94.83% on `opentele.td` (gate 90%).
- `pip install opentele-ng==1.1.0` in fresh `python:3.13-slim`: imports clean, `opentele.__version__ == "1.1.0"`, `py.typed` shipped in the wheel, `opentele-ng --version` works as a shell command.
- Cross-impl byte-identity check still green on 2 real tdata folders (TD 6.0.6 + TD 6.0.8).

## [1.0.4] - 2026-05-20 — Packaging + metadata polish (post-publish follow-up)

Zero-risk doc-level release that cleans up packaging glitches discovered after 1.0.3 went live on PyPI, plus PyPI page metadata polish (more project URLs, `Production/Stable` dev-status, additional Python implementation classifiers). No runtime behaviour change — wire-format / crypto / API surface identical to 1.0.3.

### Fixed (packaging)
- `MANIFEST.in`: added missing `include` keyword on `requirements.txt` — wheel builds from sdist were failing with `FileNotFoundError: 'requirements.txt'`. Also added explicit `include` for README.md, LICENSE, CHANGELOG.md, ACKNOWLEDGMENTS.md, SECURITY.md, `recursive-include docs/examples *.md`, and `prune tests` (sdist no longer carries half the test tree).

### Changed
- `setup.py` classifiers: `Development Status :: 4 - Beta` → `5 - Production/Stable`; added `Programming Language :: Python :: 3 :: Only` and `Programming Language :: Python :: Implementation :: CPython`.
- `setup.py` `project_urls`: now exposes Homepage, Source, Changelog, Bug Tracker, Documentation, Security (was: only `url=` Homepage). All link to the GitHub repo, so the PyPI sidebar renders proper navigation.
- `scripts/publish.sh` switched from host `pip install build twine` to a Docker container (`python:3.13-slim` with `--user $UID:$GID`). Resolves PEP 668 "externally-managed-environment" on modern host distros and keeps `dist/` artifacts owned by the invoking user. Token is passed via host env var (not argv) so it does not appear in `ps`; `.env` is sourced without `set -a` so secrets don't leak into `/proc/<pid>/environ`.

### Verified
- Cross-impl byte-identity check on 2 real tdata folders (TD 6.0.6 + TD 6.0.8) — `opentele-ng` matches `opentele-tg 3.13.1` (PyQt5, Ehekatech fork) and `opentele2 1.1.6` (pure-Python DedInc fork) **byte-for-byte** on `serializeMtpAuthorization()`, `authKey`, `localKey`, `UserId`, `MainDcId`. On TD 6.0.6 tdata, `opentele-tg` crashes (`No account has been loaded`) because it lacks Phase 1.5 lskTypes 0x1A-0x1E — confirms our wire-format fixes are load-bearing for current Telegram Desktop tdata in the wild.

## [1.0.3] - 2026-05-20 — DoS fix in MapData count loops (security)

Closes the **DoS vulnerability** documented in 1.0.2's `tests/test_dos_protection.py` xfail canaries. Phase 1.0.2 found that several count-driven loops in `MapData.read()` and `Account._setMtpAuthorization.readKeys()` had no upper-bound check on attacker-controlled `count` fields — a malformed tdata blob with `count = 0xFFFFFFFF` (~4 billion iterations) would spin for minutes consuming CPU before the trailing `ExpectStreamStatus` finally tripped.

### Fixed (security)
- **`MapData.read()`**: pre-loop `count` cap by `stream.bytesAvailable() // pair_size` in:
  - `lskDraft` branch (16 bytes/pair: FileKey + PeerId)
  - `lskDraftPosition` branch (16 bytes/pair)
  - `lskLegacyImages` / `lskLegacyStickerImages` / `lskLegacyAudios` branch (28 bytes/pair: 3 × uint64 + int32)
  - `lskBotStorages` branch (16 bytes/pair)
- **`Account._setMtpAuthorization.readKeys()`**: pre-loop cap on `key_count`. Each AuthKey is `int32 dcId + 256-byte key = 260 bytes`. Refuses to allocate unbounded loop if declared count exceeds remaining buffer.
- All guards raise `TDataReadMapDataFailed` / `QDataStreamFailed` early so `TDesktop.__loadFromTData`'s existing `except OpenTeleException` swallow path handles it cleanly (corrupt tdata → "No account has been loaded" instead of multi-minute CPU spin).

### Added
- **`QDataStream.bytesAvailable()`** (`src/td/qdatastream.py`) — delegates to `device.bytesAvailable()`. Returns 0 if no device or device exhausted. Used by the new `_GuardCount` helper.
- **`_GuardCount(count, pair_bytes, stream, key_name)`** helper at module top of `src/td/account.py`. Compact, reusable, descriptive error message includes declared count + available bytes + max pairs.

### Test impact
- 5 xfail security canaries in `tests/test_dos_protection.py` automatically flip to `PASSED` (they were already designed to do so: `time.perf_counter() < 0.5s + raise observed → assert raised`). No test code modification needed.
- 247 tests pass on Python 3.10–3.14 (6 DoS canaries now all PASS instead of 5 xfail + 1 pass).
- Coverage stable at **94.89%** on `opentele.td` (gate 90%).

### Compatibility
- Legitimate large `count` values (e.g. a real Telegram Desktop user with hundreds of drafts) still load: the cap is by `bytesAvailable` not a hardcoded limit, so any valid tdata where `count * pair_size ≤ remaining bytes` passes through unchanged. Only **malformed** blobs are rejected.

## [1.0.2] - 2026-05-20 — Test hardening (3-AI consultation)

Phase 1.0.2 follows up on the Codex/Cursor/Gemini consultation after 1.0.1 shipped. Focus is purely on test coverage and dead-code removal — no behaviour changes to the production read/write paths.

### Added
- **`tests/qdatastream/test_pure_errors.py`** (38 tests) — error-path coverage for `opentele.td.qdatastream`. The existing `tests/qdatastream/test_primitives.py` etc. used PyQt6 as the oracle and never touched our pure-Python error paths. This file directly exercises:
  - EOF on every fixed-width `readUInt*`/`readInt*` (parametrized 8 ways)
  - Status stickiness across reads + `resetStatus()` semantics
  - `QDataStream()` without device → ReadPastEnd / WriteFailed
  - `readRawData(n > available)` → short read + ReadPastEnd
  - `readQString` malformed (truncated prefix, oversized payload, odd UTF-16 byte count, isolated surrogate, null/empty markers)
  - `stream >> QByteArray` malformed — **security: huge declared size with short payload does NOT pre-allocate 4 GB**
  - QByteArray null vs empty marker semantics
  - QBuffer edges (None backing, negative seek, read past EOF)
  - QFile edges (missing path, invalid mode, closed-file stability, WriteOnly does NOT auto-create parent dirs — pinned the doc-comment behaviour Codex flagged as misleading)
  - `QDataStream(<wrong type>)` → TypeError
  - QDir helpers
- **`tests/test_dos_protection.py`** (6 tests, 5 xfail + 1 sanity pass) — **SECURITY**. Confirms a real DoS vulnerability in `MapData.read()` and `Account._setMtpAuthorization()`: malformed encrypted payloads with `count=2_000_000` and no following payload cause millions of no-op loop iterations (seconds-to-minutes of CPU depending on Python version) before the trailing `ExpectStreamStatus` raises. Tests use wall-clock measurement (`time.perf_counter()`) with a 0.5s budget — calls exceeding the budget mark themselves as xfail via in-test `pytest.xfail()` (works identically across Python 3.10-3.14). The sanity test (`test_mapdata_zero_count_does_not_loop`) confirms the test infrastructure isn't artificially slow on the happy path. Once Phase 1.0.3 fixes `MapData.read` to bail on stream-status mismatch inside the count loop, all 5 xfails will flip to expected pass.
- **`tests/test_account_property_smoke.py`** (6 tests) — trivial getter/setter coverage for `Account.keyFile`, `Account.localKey`, `Account.MtpConfig`, `Account.isAuthorized()` (account.py lines 842, 846-847, 854, 884, 891).
- **`tests/test_tdesktop_lifecycle.py`** (7 tests) — `PerformanceMode` toggle, `api` setter propagation to accounts, `AppVersion` property pre/post `LoadTData`, passcode-protected save/load roundtrip (exercises the non-performance-mode key-derivation branch at tdesktop.py:354-376), wrong-passcode → `TDataBadDecryptKey`.

### Removed (dead code)
- **`account.py:1004-1005`** — unused nested helper `def keysSize(list):` inside `serializeMtpAuthorization`. Both Codex and Cursor flagged it as never-called. Removed; saves ~2 coverage lines.

### Dependencies
- Added `pytest-timeout>=2.1` to `requirements-test.txt` (test-only, not a runtime dep).

### Coverage
- 186 → **247 tests passing** (61 new + 5 documented xfail).
- `opentele.td` aggregate coverage: 88.69% → **94.99%**.
  - `account.py`: 95% → **100%**
  - `qdatastream.py`: 79% → **91%**
  - `tdesktop.py`: 92% → **97%**
- All 5 Python versions (3.10-3.14) green with the 85% CI gate.
- CI gate ready to be ratcheted from 85% to **90%** safely (92% if user
  accepts the qdatastream.py 91% as the new floor).

### Known bugs documented (fix in 1.0.3)
- **DoS via unbounded count loops** in `MapData.read` (lskDraft/lskDraftPosition/lskBotStorages/lskLegacyImages branches) and `Account._setMtpAuthorization` `readKeys()`. See `tests/test_dos_protection.py` xfail markers. 3-AI consultation needed on fix location.

## [1.0.1] - 2026-05-19 — opentele-ng Phase 5.1 (_settingsKey magic removed)

Phase 5 deferred the upstream ``_settingsKey = FileKey(1851671142505648812)`` hardcoded magic constant fix because doing both the code change AND the test change would have violated Phase 4's "168 tests without modification" acceptance contract. With Phase 5 shipped, 1.0.1 closes that loop.

### Fixed
- **Removed upstream ``_settingsKey = FileKey(1851671142505648812)`` magic** from ``MapData.__init__``. The constant existed only to pad the encrypted descriptor past AES-IGE256's "data must be multiple of 16 bytes" requirement when the rest of MapData was empty. Default ``_settingsKey`` is now plain ``FileKey(0)``.
- **``Storage.PrepareEncrypted`` AES alignment for empty payloads**: when ``data.size() == 0`` the function now encodes the minimal valid upstream-readable ``dataLen=4`` size marker (which is what both upstream TDesktop and ``DecryptLocal``'s ``dataLen < 4`` guard require) and pads to a 16-byte AES block. Empty ``MapData`` (no lskType keys, no drafts, no bot storages) now writes and reads back correctly.

### Tests
- ``test_settingsKey_default_is_zero_no_more_magic`` — pins new default.
- ``test_empty_mapdata_with_zero_settingsKey_now_writes_successfully`` — Phase 4's "this fails" test is now "this succeeds".
- ``test_settingsKey_zero_works_alongside_other_keys`` — kept as regression guard.
- 186 tests total (was 185), coverage 77.34% on ``opentele.td``.

## [1.0.0] - 2026-05-19 — opentele-ng Phase 5 (Pure-Python QDataStream, drop PyQt6)

**USP / breaking dependency change:** opentele-ng no longer requires PyQt6 at
runtime. The handful of Qt classes opentele actually used (``QDataStream``,
``QByteArray``, ``QBuffer``, ``QFile``, ``QDir``, ``QSysInfo``,
``QIODevice.OpenModeFlag``) are now provided by ``opentele.td.qdatastream``,
a stdlib-only (``struct`` / ``pathlib`` / ``platform``) module that produces
byte-identical output with PyQt6's Qt_5_1 binary format.

This means:

* **No system Qt libraries needed.** Install opentele-ng on minimal Linux
  containers / Alpine / serverless without ``libgl1`` / ``libegl1`` /
  ``libxkbcommon-x11-0`` etc.
* **Python 3.14 first-class.** PyQt6 6.6+ does support 3.14, but with extra
  system-deps friction; pure-Python avoids that.
* **Smaller install footprint.** ``telethon + tgcrypto-pyrofork`` only — no
  ~50 MB Qt wheels.
* **PyPy / experimental interpreters** become reachable.

### Added
- **``src/td/qdatastream.py``** — 600+ lines of byte-identical pure-Python
  replacements:
  - ``QByteArray(bytearray)`` — preserves ``isNull()`` semantics while
    inheriting buffer protocol so ``hashlib.sha1(qba)`` and
    ``tgcrypto.ige256_encrypt(qba, ...)`` work unchanged.
  - ``QDataStream`` Qt_5_1 wire format: big-endian fixed-width int8/16/32/64,
    uint variants, ``writeInt32`` two's complement, ``QString`` as
    ``uint32 size_in_bytes + UTF-16-BE``, ``QByteArray`` as
    ``uint32 size + payload`` with ``0xFFFFFFFF`` null marker and
    ``0x00000000`` empty marker, ``readRawData`` / ``writeRawData`` verbatim.
  - ``QBuffer`` — cursor over a ``QByteArray`` (read/write, seek, pos,
    isOpen, atEnd).
  - ``QFile`` — open()-backed file wrapper.
  - ``QDir`` — pathlib wrapper (exists / mkpath).
  - ``QSysInfo.Endian.ByteOrder`` — host byte order detected at import time
    so the md5 fingerprint in ``FileWriteDescriptor.writeData`` matches what
    TDesktop produces on the same host.

### Changed
- **``requirements.txt``**: removed ``PyQt6>=6.6``. Runtime deps reduced to
  ``telethon>=1.36,<2`` + ``tgcrypto-pyrofork>=1.2.7``.
- **``requirements-test.txt``**: kept ``PyQt6>=6.6`` as a **test-only**
  dependency. The 40+ tests in ``tests/qdatastream/`` use PyQt6 directly as
  the byte-identity oracle against the pure-Python replacement.
- ``src/exception.py``: imports ``QDataStream`` from
  ``opentele.td.qdatastream`` instead of ``PyQt6.QtCore``.
- ``src/td/configs.py``: same rewire for ``QBuffer``, ``QByteArray``,
  ``QDataStream``, ``QDir``, ``QFile``, ``QIODevice``, ``QSysInfo``.
- ``setup.py``: version 0.4.0 → **1.0.0** (major bump, breaking dep change).
  Description updated with the no-Qt USP. Classifier
  ``Development Status`` 4-Beta → 5-Production/Stable.

### Acceptance criteria met
- All 168 existing Phase 4 tests pass **without modification** — this was
  the safety-net contract of Phase 4 (40 goldens + property-based fuzzing
  + real ``MapData`` roundtrips). Verified on Python 3.10/3.11/3.12/3.13/3.14.
- ``opentele.td`` package coverage: **76.70%** (gate 75% — passes; Phase 4 was 78%, slight drop expected due to new 769-line qdatastream.py with error-handling branches not exercised by valid tdata fixtures).
- ``pip install opentele-ng`` installs without PyQt6 in transitive deps.
- ``ruff check src/ tests/`` clean.

### Known deviation from spec
- The ``MapData._settingsKey = FileKey(1851671142505648812)`` hardcoded
  magic constant is **kept as-is** because the Phase 4 test
  ``test_settingsKey_is_required_when_map_is_otherwise_empty`` *expects*
  ``ValueError`` when the map is empty + ``_settingsKey=0`` (which proves
  the magic is still load-bearing). Replacing it with AES-padding in
  ``EncryptedDescriptor`` is left for a future minor release that can also
  update that test in the same commit. The Phase 5 acceptance criterion of
  "all 168 tests pass without modification" rules out doing both at once.

### PyQt6 status post-Phase-5
- **Runtime:** not installed, not imported, not in ``install_requires``.
- **Test-time only:** ``tests/qdatastream/`` and several ``tests/test_account_*``
  modules import ``PyQt6.QtCore`` directly to compare bytes against the new
  pure-Python implementation. CI install path is ``pip install -e . &&
  pip install -r requirements-test.txt``.

## [0.4.0] - 2026-05-19 — opentele-ng Phase 4 (test infrastructure / TDD safety net)

Phase 4 builds the safety net required before Phase 5 can drop PyQt for a pure-Python QDataStream rewrite. **48 new tests** — golden bytes for every QDataStream primitive, property-based fuzzing via hypothesis (~1000 random cases per run), and real `TDesktop.SaveTData → load` roundtrips through `MapData.prepareToWrite()`.

### Added
- **`tests/qdatastream/`** (3 files, 40 tests):
  - `test_primitives.py` (21 tests) — golden byte layouts for `writeUInt8/16/32/64`, `writeInt32/64` (two's complement), status semantics (`Ok`/`ReadPastEnd`). Verifies Qt_5_1 big-endian, fixed sizes (uint32 always 4 bytes, uint64 always 8 bytes).
  - `test_qbytearray.py` (11 tests) — `QByteArray` 4-byte size prefix, null-marker (`0xFFFFFFFF` = default-constructed), empty payload, binary payloads with null bytes, large 10KB roundtrip, two-`QByteArray` stream layout (lskWebviewTokens pattern).
  - `test_property_based.py` (8 tests) — `hypothesis` fuzzing: uint64/int32 lists, mixed-type streams, QByteArray with random binary up to 4KB. ~1000 cases per test invocation.
- **`tests/mapdata/test_real_roundtrip.py`** (8 tests) — real `TDesktop.SaveTData(tmp_path)` → fresh `TDesktop(basePath=tmp_path)`:
  - empty roundtrip
  - synthetic scalar lskType keys (`_locationsKey`, `_trustedBotsKey`, ..., and Phase 1.5 keys `_prefsKey`/`_roundPlaceholder`/`_inlineBotsDownloads`/`_mediaLastPlaybackPositions`)
  - `_webviewStorageToken*` QByteArray payloads byte-identical
  - `_botStoragesMap` Dict[PeerId, FileKey]
  - `_draftsMap` / `_draftCursorsMap`
  - documents `_settingsKey = FileKey(1851671142505648812)` magic — actually load-bearing: empty `EncryptedDescriptor` produces 0-byte payload that fails `tgcrypto.ige256_encrypt` with "data must be multiple of 16 bytes"; the magic gives ≥12 bytes so AES padding works. Phase 5 task: replace with `td.Storage.RandomGenerate(8)` or pad empty maps to AES block.
- **`requirements-test.txt`** — pinned dev deps: `pytest ≥7`, `pytest-cov ≥4`, `pytest-asyncio ≥0.21`, `hypothesis ≥6`, `ruff ≥0.5`.
- `Dockerfile.test` now copies `docs/` so QR docs tests don't break.

### Coverage
- `opentele.td` package coverage: **~78%** (whole package, including legacy mtp.py DcOptions code which is 38% covered). CI gate set to **75%** (honest threshold post Phase 4.5 measurement). Phase 5 can raise it as the rewrite forces broader coverage.
- Total tests: 98 → **146** (+48).
- All green on Python 3.10/3.11/3.12/3.13/3.14 Docker matrix.

### Phase 5 readiness
- Every `QDataStream` operation `src/td/` uses is covered by goldens or property tests.
- Pure-Python rewrite in Phase 5 must produce byte-identical output for these tests **without any test-code modification** — that's the acceptance criterion.

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