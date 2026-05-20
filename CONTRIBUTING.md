# Contributing to opentele-ng

Thanks for taking the time to contribute. This document describes how the project is structured and what we expect from PRs.

## Quick start (Docker)

The project is tested entirely in Docker — please don't `pip install` into your host Python. The CI matrix runs Python 3.10/3.11/3.12/3.13/3.14 on Ubuntu/macOS/Windows; the same images can run locally.

```bash
git clone https://github.com/stufently/opentele
cd opentele

# Build + run the full test suite (Python 3.13 by default)
docker build -f Dockerfile.test -t opentele-test .
docker run --rm opentele-test pytest --tb=short

# Lint
docker run --rm -v "$PWD:/work" -w /work python:3.13-slim bash -c \
    "pip install -q ruff && ruff check ."
```

## What kind of changes are welcome

| Likely accepted                                          | Likely rejected                                                          |
|----------------------------------------------------------|--------------------------------------------------------------------------|
| Real Telegram Desktop wire-format compatibility fixes    | "Modernize" PRs that change public API without a wire-format motivation  |
| New `lskType` keys observed in current TDesktop releases | PRs that re-introduce `PyQt5/PyQt6` as a **runtime** dependency          |
| Tests against synthetic edge-case tdata                  | "Drive-by" lint cleanups across unrelated files                          |
| DoS / OOM regression canaries                            | Stylistic refactors of crypto / wire-format code without test changes    |
| Type annotation tightening                               | New runtime dependencies without a clear, narrow use case                |

## Design constraints (please honor)

- **No Qt at runtime.** `src/td/qdatastream.py` is a byte-identical pure-Python replacement; cross-comparison tests in `tests/qdatastream/test_pure_vs_pyqt_equivalence.py` use PyQt6 only as a test-time oracle.
- **TDD.** New features arrive as a failing test → implementation → green. Wire-format changes specifically should fail a golden-byte test before they pass.
- **3-AI parallel review** (Codex / Cursor / Gemini) is applied to every PR that touches `src/td/` or `src/utils.py`. Catches from review get applied before merge.
- **Coverage gate** is 90% on `opentele.td`. Don't lower it without explanation.

## Filing issues

- For wire-format mismatches: attach a `tests/integration/` script that demonstrates the desync.
- For DoS / OOM concerns: please use the private channel described in [`SECURITY.md`](SECURITY.md), not a public issue.
- For "doesn't work on Python 3.X" reports: include `pip freeze`, the full traceback, and the output of `opentele-ng info <tdata>` if possible.

## Commit conventions

- Subject ≤ 50 chars, imperative mood, lowercase verb.
- No `Co-Authored-By` trailers.
- No `--amend` of pushed commits.
- For releases: a separate `release X.Y.Z: <one-line summary>` commit on `main` is followed by a tag `vX.Y.Z(-suffix)?` and a GitHub Release.

## Code of Conduct

This project follows the [Contributor Covenant 2.1](CODE_OF_CONDUCT.md). Be kind, assume good faith, prefer the strongest plausible interpretation of someone's PR.
