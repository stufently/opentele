"""Phase 6 — triage logic of `scripts/fork_watch.py`.

The sweep exists to stop forks from going unreviewed. Two ways that can fail
silently, both covered here: a fork that was reviewed once and then gained new
commits must come back, and a fork that could not be compared at all must not
be mistaken for "nothing to see".

Network calls are stubbed — these are tests of the decision logic, not of
GitHub.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "fork_watch.py"

if not SCRIPT.exists():  # nocov - scripts/ is not shipped in the wheel
    pytest.skip("scripts/fork_watch.py not present", allow_module_level=True)

_spec = importlib.util.spec_from_file_location("fork_watch", SCRIPT)
fork_watch = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(fork_watch)


def _fork(name: str) -> dict:
    return {"full_name": name, "stargazers_count": 0, "pushed_at": "2026-01-01T00:00:00Z",
            "default_branch": "main"}


def _compare(head: str, ahead: int = 2) -> dict:
    return {
        "ahead": ahead,
        "behind": 0,
        "head": head,
        "commits": [{"sha": head[:7], "date": "2026-01-01", "message": "some work"}],
    }


@pytest.fixture
def triage(monkeypatch):
    """Point the module's triage tables at a known two-fork universe."""
    monkeypatch.setattr(fork_watch, "TRIAGED_FORKS", {"someone/opentele": "reviewed: nothing new"})
    monkeypatch.setattr(fork_watch, "TRIAGED_HEADS", {"someone/opentele": "a" * 40})
    return fork_watch


def test_reviewed_fork_at_same_head_is_collapsed(triage, monkeypatch) -> None:
    monkeypatch.setattr(triage, "compare_to_upstream", lambda f: _compare("a" * 40))

    lines, untriaged = triage.divergence_sweep([_fork("someone/opentele")])

    assert untriaged == 0
    assert "Already triaged (1)" in "\n".join(lines)


def test_reviewed_fork_that_moved_comes_back(triage, monkeypatch) -> None:
    """A new commit changes the head — the old verdict must not keep it hidden."""
    monkeypatch.setattr(triage, "compare_to_upstream", lambda f: _compare("b" * 40))

    lines, untriaged = triage.divergence_sweep([_fork("someone/opentele")])
    body = "\n".join(lines)

    assert untriaged == 1
    assert "Moved since review" in body
    assert "reviewed: nothing new" in body, "the earlier verdict gives the reader context"


def test_moved_fork_keeps_its_verdict_even_with_no_listable_commits(
    triage, monkeypatch
) -> None:
    """Merge commits are filtered as noise. If that empties the list, the fork
    is still untriaged — and must still carry its earlier verdict, which an
    early `continue` used to swallow."""
    moved = _compare("b" * 40)
    moved["commits"] = []
    monkeypatch.setattr(triage, "compare_to_upstream", lambda f: moved)

    lines, untriaged = triage.divergence_sweep([_fork("someone/opentele")])
    body = "\n".join(lines)

    assert untriaged == 1
    assert "Moved since review" in body
    assert "reviewed: nothing new" in body


def test_unknown_fork_is_untriaged(triage, monkeypatch) -> None:
    monkeypatch.setattr(triage, "compare_to_upstream", lambda f: _compare("c" * 40))

    _lines, untriaged = triage.divergence_sweep([_fork("stranger/opentele")])

    assert untriaged == 1


def test_fork_not_ahead_is_ignored(triage, monkeypatch) -> None:
    monkeypatch.setattr(triage, "compare_to_upstream", lambda f: _compare("d" * 40, ahead=0))

    _lines, untriaged = triage.divergence_sweep([_fork("stranger/opentele")])

    assert untriaged == 0


def test_compare_error_counts_as_needing_attention(triage, monkeypatch) -> None:
    """An unchecked fork is exactly the blind spot this sweep exists to close,
    so it must not report has_activity=false and file no issue."""
    monkeypatch.setattr(triage, "compare_to_upstream", lambda f: {"_error": "404 Not Found"})

    lines, untriaged = triage.divergence_sweep([_fork("gone/opentele")])

    assert untriaged == 1
    assert "Compare errors" in "\n".join(lines)


def test_our_own_fork_is_skipped(triage, monkeypatch) -> None:
    called = []
    monkeypatch.setattr(triage, "compare_to_upstream",
                        lambda f: called.append(f) or _compare("e" * 40))

    _lines, untriaged = triage.divergence_sweep([_fork("stufently/opentele")])

    assert untriaged == 0
    assert not called, "must not spend an API call on our own fork"


def test_every_triaged_fork_has_a_recorded_head() -> None:
    """A verdict without a head would collapse that fork forever — the exact
    regression this keying was introduced to prevent."""
    missing = sorted(set(fork_watch.TRIAGED_FORKS) - set(fork_watch.TRIAGED_HEADS))
    assert not missing, (
        f"forks with a verdict but no reviewed head: {missing}. "
        "Regenerate with `python scripts/fork_watch.py --print-heads`."
    )
