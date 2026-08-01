"""Phase 6 — triage logic of `scripts/fork_watch.py`.

The sweep exists to stop forks from going unreviewed. Two ways that can fail
silently, both covered here: a fork that was reviewed once and then gained new
commits must come back, and a fork that could not be compared at all must not
be mistaken for "nothing to see".

Network calls are stubbed — these are tests of the decision logic, not of
GitHub.
"""
from __future__ import annotations

import datetime as dt
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


def test_truncated_compare_still_reports_the_fork_tip(monkeypatch) -> None:
    """GitHub caps `compare.commits` at 250 while `total_commits` reports the
    real number — but it drops the *oldest* commits, so the last entry is the
    tip even for a fork thousands of commits ahead (verified against the live
    API: torvalds/linux v6.0...v6.1 returns 250 of 10000 and ends on the v6.1
    commit). Treating a truncated response as "head unknown" would put every
    big fork back in the report every single month."""
    tip = "f" * 40
    listed = [
        {"sha": f"{i:040x}", "commit": {"message": f"c{i}", "author": {"date": "2026-01-01T00:00:00Z"}}}
        for i in range(249)
    ] + [{"sha": tip, "commit": {"message": "tip", "author": {"date": "2026-01-02T00:00:00Z"}}}]
    monkeypatch.setattr(fork_watch, "gh_get", lambda path: {
        "ahead_by": 400, "behind_by": 0, "total_commits": 400, "commits": listed,
    })

    result = fork_watch.compare_to_upstream(_fork("busy/opentele"))

    assert result["ahead"] == 400
    assert result["head"] == tip


def test_compare_without_listable_commits_has_no_head(monkeypatch) -> None:
    """No commits at all is the one case where there is no tip to key on."""
    monkeypatch.setattr(fork_watch, "gh_get", lambda path: {
        "ahead_by": 1, "behind_by": 0, "total_commits": 1, "commits": [],
    })

    assert fork_watch.compare_to_upstream(_fork("odd/opentele"))["head"] == "unknown"


def test_empty_commit_message_does_not_abort_the_run(monkeypatch) -> None:
    """`git commit --allow-empty-message` is legal; an IndexError here would
    take down the whole monthly report and file no issue at all."""
    monkeypatch.setattr(fork_watch, "gh_get", lambda path: [
        {"sha": "b" * 40, "commit": {"message": "", "author": {"date": "2026-01-01T00:00:00Z"}}},
    ])

    commits = fork_watch.recent_commits("someone/opentele", dt.datetime(2026, 1, 1))

    assert commits == [{"sha": "b" * 7, "date": "2026-01-01T00:00:00Z", "message": ""}]


def test_every_triaged_fork_has_a_recorded_head() -> None:
    """A verdict without a head would collapse that fork forever — the exact
    regression this keying was introduced to prevent."""
    missing = sorted(set(fork_watch.TRIAGED_FORKS) - set(fork_watch.TRIAGED_HEADS))
    assert not missing, (
        f"forks with a verdict but no reviewed head: {missing}. "
        "Regenerate with `python scripts/fork_watch.py --print-heads`."
    )
