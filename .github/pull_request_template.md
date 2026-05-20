<!-- One-sentence summary of the change. -->

## Summary

## Why

<!-- The motivation. For wire-format changes, please link to the TDesktop source line or behavior you're matching. -->

## Test plan

- [ ] `pytest --tb=short` passes locally
- [ ] `ruff check src/ tests/ --no-cache` clean (run from a fresh container without the `opentele -> src` symlink — see CONTRIBUTING.md)
- [ ] If this touches `src/td/` or `src/utils.py`: 3-AI review (Codex + Cursor + Gemini) requested

## Checklist

- [ ] No PyQt runtime dependency reintroduced
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] New tests added (or explained why not)
- [ ] No secrets, real auth keys, or session tokens in test fixtures
