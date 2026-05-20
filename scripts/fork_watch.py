"""Monthly fork sweep — find commits in other forks of thedemons/opentele that
might be worth pulling into opentele-ng.

Runs from GitHub Actions (see .github/workflows/forks-watch.yml). Output is a
Markdown report; the calling workflow opens it as a GitHub Issue so it lands
in the maintainer's inbox.

No secrets needed beyond the default GITHUB_TOKEN — we only read public
metadata of public repos.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

UPSTREAM = "thedemons/opentele"
LOOKBACK_DAYS = 35
GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN")

# Forks we already learned from / share an ancestor — no need to re-flag the
# same well-known commits each month.
KNOWN_FORKS = {
    "stufently/opentele",       # us
    "thedemons/opentele",
}

# Commit messages that mean "merged thedemons:main into our fork" rather than
# real local work — filter these out.
NOISE_MESSAGES = (
    "Merge branch 'thedemons:main'",
    "Merge pull request #",
)


def gh_get(path: str) -> object:
    """GET https://api.github.com/<path>. Returns dict on error envelopes."""
    url = f"{GITHUB_API}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "opentele-ng-forks-watch",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def list_forks(repo: str) -> list[dict]:
    out: list[dict] = []
    for page in range(1, 4):  # cap at 300 forks; upstream has <200
        chunk = gh_get(f"repos/{repo}/forks?per_page=100&sort=newest&page={page}")
        if not isinstance(chunk, list):
            # GitHub returns a dict on rate limit / auth failure.
            msg = chunk.get("message", "non-list response") if isinstance(chunk, dict) else "?"
            print(f"WARN: forks page {page} returned non-list: {msg}", file=sys.stderr)
            break
        if not chunk:
            break
        out.extend(chunk)
        if len(chunk) < 100:
            break
    return out


def recent_commits(repo_full_name: str, since: dt.datetime) -> list[dict]:
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        commits = gh_get(f"repos/{repo_full_name}/commits?since={since_iso}&per_page=20")
    except urllib.error.HTTPError as exc:
        return [{"_error": f"{exc.code} {exc.reason}"}]
    if not isinstance(commits, list):
        return [{"_error": "non-list response"}]
    out: list[dict] = []
    for c in commits:
        msg = (c.get("commit", {}).get("message") or "").splitlines()[0]
        if any(noise in msg for noise in NOISE_MESSAGES):
            continue
        out.append({
            "sha": c.get("sha", "")[:7],
            "date": c.get("commit", {}).get("author", {}).get("date", ""),
            "message": msg[:120],
        })
    return out


def main() -> int:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=LOOKBACK_DAYS)
    print(f"# Forks watch — {dt.date.today().isoformat()}", file=sys.stdout)
    print(file=sys.stdout)
    print(f"Looking at commits in forks of `{UPSTREAM}` pushed since `{cutoff.date()}` "
          f"({LOOKBACK_DAYS} days ago).", file=sys.stdout)
    print(file=sys.stdout)

    try:
        forks = list_forks(UPSTREAM)
    except urllib.error.HTTPError as exc:
        print(f"GitHub API error listing forks: {exc.code} {exc.reason}", file=sys.stderr)
        return 1

    candidates = [
        f for f in forks
        if f["full_name"] not in KNOWN_FORKS
        and (f.get("pushed_at") or "") >= cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    ]
    candidates.sort(key=lambda f: f.get("pushed_at") or "", reverse=True)

    if not candidates:
        print(f"No fork pushed anything new in the last {LOOKBACK_DAYS} days. "
              "Nothing to triage this month.", file=sys.stdout)
        # Signal "skip issue" to the workflow.
        gha_out = os.environ.get("GITHUB_OUTPUT")
        if gha_out:
            with open(gha_out, "a") as fh:
                fh.write("has_activity=false\n")
        return 0

    print(f"## {len(candidates)} fork(s) with activity\n", file=sys.stdout)
    print("| Fork | ⭐ | Last push | New commits |", file=sys.stdout)
    print("|------|---:|-----------|-------------|", file=sys.stdout)

    details: list[str] = []
    errors: list[str] = []
    for f in candidates:
        full = f["full_name"]
        stars = f.get("stargazers_count", 0)
        pushed = (f.get("pushed_at") or "")[:10]
        commits = recent_commits(full, cutoff)
        link = f"[`{full}`](https://github.com/{full})"
        if commits and "_error" in commits[0]:
            errors.append(f"- `{full}` — {commits[0]['_error']}")
            print(f"| {link} | {stars} | {pushed} | (api error) |", file=sys.stdout)
            continue
        n = len(commits)
        print(f"| {link} | {stars} | {pushed} | {n} |", file=sys.stdout)
        if commits:
            details.append(f"\n### {full}\n")
            for c in commits[:8]:
                details.append(f"- `{c['sha']}` {c['date'][:10]} — {c['message']}")

    if errors:
        print("\n## API errors\n", file=sys.stdout)
        for line in errors:
            print(line, file=sys.stdout)

    if details:
        print("\n## Commit details (top 8 per fork)\n", file=sys.stdout)
        for line in details:
            print(line, file=sys.stdout)

    print("\n---\n", file=sys.stdout)
    print("Open these forks and skim commits. Pull anything that:", file=sys.stdout)
    print("- fixes a real wire-format bug in current Telegram Desktop tdata,", file=sys.stdout)
    print("- adds a missing lskType key,", file=sys.stdout)
    print("- closes a CVE-class issue (DoS / OOM / path traversal).", file=sys.stdout)
    print("\nIgnore (already covered in opentele-ng):", file=sys.stdout)
    print("- PyQt5→PyQt6 migrations,", file=sys.stdout)
    print("- Py3.13 dunders (`__firstlineno__` / `__static_attributes__`) in extend_class,", file=sys.stdout)
    print("- `await _on_login` adjustments — opentele-ng auto-detects Awaitable.", file=sys.stdout)

    gha_out = os.environ.get("GITHUB_OUTPUT")
    if gha_out:
        with open(gha_out, "a") as fh:
            fh.write("has_activity=true\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
