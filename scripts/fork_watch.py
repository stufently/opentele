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
import time
import urllib.error
import urllib.request

UPSTREAM = "thedemons/opentele"
UPSTREAM_BRANCH = "main"
LOOKBACK_DAYS = 35
GITHUB_API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN")

# Forks we already learned from / share an ancestor — no need to re-flag the
# same well-known commits each month.
KNOWN_FORKS = {
    "stufently/opentele",       # us
    "thedemons/opentele",
}

# Forks whose divergence has been read and ruled on, keyed by the head commit
# that was reviewed. The divergence sweep collapses them so only genuinely new
# work needs attention — but a *new* commit changes the head SHA, which drops
# the fork back into "untriaged". Keying by repo name alone would mean a fork
# reviewed once is trusted forever, recreating the very blind spot below.
#
# The recency section alone could never surface these: a fork that went ahead
# in 2024 and was never touched again has no push inside the lookback window,
# so it stayed invisible to every monthly report. The 2026-07-29 manual sweep
# of all 124 forks found exactly that class of miss — hence this section.
#
# `TRIAGED_HEADS` holds the fork tip that was actually read, filled in from a
# live run (`--print-heads`). A fork listed in `TRIAGED_FORKS` but missing here
# stays collapsed until it moves; once its head differs from the recorded one,
# it is reported as untriaged again with the note attached for context.
TRIAGED_FORKS: dict[str, str] = {
    "timka-123/opentele": "2026-07-29: Pyrogram conversion — idea adopted (implemented "
                          "cleanly here), their code is broken (NameError, multi-DC "
                          "serialization, AuthKey(.key))",
    "pypchuk/opentele": "2026-07-29: fsspec filesystem abstraction — idea noted, code "
                        "mixes QFile API with fsspec handles and breaks TDesktop.__init__",
    "HamzaLiu/opentele": "2026-07-29: **kwargs→QRLoginToNewClient already here (Phase 3); "
                         "its QDataStream.Status.Ok→.Ok is PyQt5-only, would break PyQt6",
    "Paramon/opentele": "2026-07-29: device/app_version refresh — adopted in Phase 2, "
                        "ours is newer",
    "anmv/opentele": "2026-07-29: same lineage as Paramon; layer-pinning idea adopted "
                     "properly (TELEGRAM_DESKTOP_LAYERS)",
    "RobertAzovski/opentele": "2026-07-29: lskTypes 0x1A-0x1D — adopted in 1.2.x",
    "Snowing/opentele": "2026-07-29: lskBackgroundOldOld fix — adopted in 1.2.x",
    "gfhfyjbr/opentele": "2026-07-29: lskCustomEmojiKeys/SearchSuggestions/WebviewTokens "
                         "— already here (0x17-0x19)",
    "ovflw/opentele": "2026-07-29: same lskTypes as gfhfyjbr — already here",
    "AlreadyNobody/OpenTele-3.13": "2026-07-29: py3.13 dunder fix already here; its "
                                   "api.pid→api.device_model change disables the APIData hook",
    "feb-cloud/opentele": "2026-07-29: py3.13 dunder fix — already here",
    "kr-aleksey/opentele-fix": "2026-07-29: py3.13 fix — already here",
    "azamtoiri/opentele": "2026-07-29: PyQt6 + py3.13 — already here",
    "ibrohimtoiri/opentele": "2026-07-29: PyQt6 + py3.13 — already here",
    "WeslenPy/opentele": "2026-07-29: PyQt6 — already here",
    "skybots-tg/opentele": "2026-07-29: PyQt6 — already here",
    "L4puta/opentele": "2026-07-29: PyQt6 — already here",
    "AstralMortem/opentele": "2026-07-29: PySide6 + poetry, pinned <3.13 — regression for us",
    "real-LiHua/opentele": "2026-07-29: `keyFile and kDefaultKeyFile` ignores custom "
                           "keyFile — bug, do not take",
    "Vladoha33/opentele": "2026-07-29: `raise (str) from e` — raises TypeError, do not take",
    "alberjo/shared-opentele": "2026-07-29: removes extend_class conflict detection",
    "sstecho/opentele": "2026-07-29: reindentation only",
    "Ehekatech/opentele-tg": "2026-07-29: reviewed in 1.3.2 sweep — await _on_login, "
                             "scaffolding deletions",
    "pyhashem/tlapi": "2026-07-29: rebrand + device pruning, nothing new",
    "1Danish-00/opentele": "2026-07-29: pins a personal telethon fork",
    "Arkptz/opentele": "2026-07-29: nix/poetry packaging only",
    "snakechilds/opentele-nuitka": "2026-07-29: nuitka packaging; kwargs idea already here",
    "MoriSummerz/opentele-wo-pyqt": "2026-07-29: drops td from __init__ to avoid PyQt",
    "3hx/opentele": "2026-07-29: poetry + PyQt5 rollback",
    "linhhd1kt/opentele-makele": "2026-07-29: CI yaml only",
    "eyMarv/OpenTele": "2026-07-29: docs/rename only",
    "fmu1337/opentele": "2026-07-29: 2023 app versions — stale",
    "Derivability/opentele": "2026-07-29: recursion fix superseded upstream",
    "oldemerson/opentele": "2026-07-29: 2022 api.py tweak",
    "zulfiqor1-1/opentele-m": "2026-07-29: 2023 api.py tweak",
    "Pavel-qr/opentele": "1.3.2 sweep: py3.13 dunders already here; its device/version "
                         "refresh is older than ours and sets kMaxAccounts=150 (real cap is 6)",
    "SychO3/opentele": "2026-07-29: requirements.txt pins only",
}

# Fork tip that was reviewed, per fork. Regenerate with:
#     GITHUB_TOKEN=... python scripts/fork_watch.py --print-heads
TRIAGED_HEADS: dict[str, str] = {
    "1Danish-00/opentele": "9e594951f1412f8e3f68862186507a48c83d23e9",
    "3hx/opentele": "22e1ec81a27e49d6bc806b0cae6878a352d5b413",
    "AlreadyNobody/OpenTele-3.13": "10f551859b84f380fc69978b729c949173fe0810",
    "Arkptz/opentele": "b2d0d95f691970ef0a9dade8516d7703ff8e9a04",
    "AstralMortem/opentele": "36ebc3a01b2a4f2ed958195be81ff0fccf114b73",
    "Derivability/opentele": "9a5c6383d8ff5dfeafb941edd4f48674922dfaa8",
    "Ehekatech/opentele-tg": "ddc03011eb9886ccbfd99e835da9da04c05d6783",
    "HamzaLiu/opentele": "034f0fa884abdde3adb54c5e581c9b0f0a80ee56",
    "L4puta/opentele": "ee070b548382196414a4799ea95b9c712569092b",
    "MoriSummerz/opentele-wo-pyqt": "25e00d6f52aa883a738c28342dcaf68470ace1bd",
    "Paramon/opentele": "927db275b6418ee55c080f5698a8687abb7518b1",
    "Pavel-qr/opentele": "e9ad22c8502de897e93fef589e0ca5ba687a2ce0",
    "RobertAzovski/opentele": "3f6e5dfe758544767075509cab8e117761ebad4e",
    "Snowing/opentele": "4586f81249f517943b101e779b0b4262634cb81d",
    "SychO3/opentele": "f886924a8a5ab1dc4b87c1667a78564b39fb80d7",
    "Vladoha33/opentele": "f6c39fffe7eef640a4f59643ed69148c444a5422",
    "WeslenPy/opentele": "99b2e99175df088efc6dfdc5072978c717f6b642",
    "alberjo/shared-opentele": "d23a6870fa6a8a0d78e1ee8734db0fa054b78662",
    "anmv/opentele": "4df17bd8c443d6452afc5a2d29ec7922fad1a5c3",
    "azamtoiri/opentele": "383eaed299b8190693d531a1c14b759505002610",
    "eyMarv/OpenTele": "7d60a5e9dca41136595dfc701858ab8e32165475",
    "feb-cloud/opentele": "ba53edbfdb31e1d72a5ee701e723f33df59b1da4",
    "fmu1337/opentele": "03c6a2c884d9b8980c28728f5372085e96dbbad4",
    "gfhfyjbr/opentele": "db8eae1655488a12e1c704fb6839ea6801c01131",
    "ibrohimtoiri/opentele": "383eaed299b8190693d531a1c14b759505002610",
    "kr-aleksey/opentele-fix": "c57bc7b5fcc89e2b553627996390dc12c9178a21",
    "linhhd1kt/opentele-makele": "9b2213883339edc7d5cecfffd1361048eaec0f7f",
    "oldemerson/opentele": "84e43c484972b5d201e8a997e93239472d945dd6",
    "ovflw/opentele": "807e217e6b7b8601cdc101929ceb458f8ae574c2",
    "pyhashem/tlapi": "ffd2402d3cbfd3a980c4fcd9ca784757df0fc417",
    "pypchuk/opentele": "fe503f87d93e93ee5fc1688814d12c523c818d0e",
    "real-LiHua/opentele": "85d832dbb8691f54a7edc5923504300f9285c04f",
    "skybots-tg/opentele": "2594fa43b624226bc12a054043ba1c9f91ffa83a",
    "snakechilds/opentele-nuitka": "0e1cddf526b0abaea2c8dee0a01b7088275c6aa6",
    "sstecho/opentele": "2ccdb273942d11bf500bf58e83ea3399b486fbfe",
    "timka-123/opentele": "785e509bb0a9962d9c0d416554c4fe432129a4dd",
    "zulfiqor1-1/opentele-m": "c22a25f3b92ba3646a00b588c62e8530a8e81bb7",
}

# Commit messages that mean "merged thedemons:main into our fork" rather than
# real local work — filter these out.
NOISE_MESSAGES = (
    "Merge branch 'thedemons:main'",
    "Merge pull request #",
)


def gh_get(path: str, retries: int = 2) -> object:
    """GET https://api.github.com/<path>. Returns dict on error envelopes.

    Transient transport failures are retried: this runs unattended once a
    month over ~150 requests, and a single timed-out socket used to abort the
    whole report with a traceback and no issue filed. `HTTPError` is *not*
    retried — status codes are the callers' business (404 = fork we cannot
    read, 403 = rate limit).
    """
    url = f"{GITHUB_API}/{path.lstrip('/')}"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "opentele-ng-forks-watch",
        **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
    })
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == retries:
                raise
            print(f"WARN: {path} — {exc}; retry {attempt + 1}/{retries}", file=sys.stderr)
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")  # nocov


def list_forks(repo: str) -> list[dict]:
    """Paginate ALL forks (not just first N pages of 'newest'). Codex noted
    that 'sort=newest' orders by creation, so an OLD fork with a RECENT push
    can be missed if it doesn't fit in the first 100. Sort locally by
    ``pushed_at`` instead.
    """
    out: list[dict] = []
    for page in range(1, 11):  # up to 1000 forks (upstream has <200 as of 2026-05)
        chunk = gh_get(f"repos/{repo}/forks?per_page=100&page={page}")
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
    out.sort(key=lambda f: f.get("pushed_at") or "", reverse=True)
    return out


def recent_commits(repo_full_name: str, since: dt.datetime) -> list[dict]:
    since_iso = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        commits = gh_get(f"repos/{repo_full_name}/commits?since={since_iso}&per_page=20")
    except urllib.error.HTTPError as exc:
        return [{"_error": f"{exc.code} {exc.reason}"}]
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        return [{"_error": f"transport: {exc}"}]
    if not isinstance(commits, list):
        return [{"_error": "non-list response"}]
    out: list[dict] = []
    for c in commits:
        msg = ((c.get("commit", {}).get("message") or "").splitlines() or [""])[0]
        if any(noise in msg for noise in NOISE_MESSAGES):
            continue
        out.append({
            "sha": c.get("sha", "")[:7],
            "date": c.get("commit", {}).get("author", {}).get("date", ""),
            "message": msg[:120],
        })
    return out


def compare_to_upstream(fork: dict) -> dict:
    """How far ahead of `UPSTREAM:main` this fork is, regardless of *when*.

    Returns ``{"ahead": int, "behind": int, "commits": [...]}`` or
    ``{"_error": str}``. A fork whose default branch was deleted, or that is a
    fork of a fork, makes the compare endpoint 404 — that is not an outage,
    just a fork we cannot read, so it is reported and skipped.
    """
    full = fork["full_name"]
    owner = full.split("/")[0]
    branch = fork.get("default_branch") or UPSTREAM_BRANCH
    try:
        data = gh_get(f"repos/{UPSTREAM}/compare/{UPSTREAM_BRANCH}...{owner}:{branch}")
    except urllib.error.HTTPError as exc:
        return {"_error": f"{exc.code} {exc.reason}"}
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        # One unreachable fork must not cost us the other 130.
        return {"_error": f"transport: {exc}"}
    if not isinstance(data, dict) or "ahead_by" not in data:
        return {"_error": "unexpected compare payload"}
    commits = []
    for c in data.get("commits") or []:
        msg = ((c.get("commit", {}).get("message") or "").splitlines() or [""])[0]
        if any(noise in msg for noise in NOISE_MESSAGES):
            continue
        commits.append({
            "sha": c.get("sha", "")[:7],
            "date": (c.get("commit", {}).get("author", {}) or {}).get("date", "")[:10],
            "message": msg[:120],
        })
    all_commits = data.get("commits") or []
    return {
        "ahead": data.get("ahead_by", 0),
        "behind": data.get("behind_by", 0),
        "commits": commits,
        # Fork tip. `compare` returns commits oldest-first and caps the list at
        # 250 while `total_commits` reports the real number — but it drops the
        # *oldest* ones, so the last entry is the head even when truncated
        # (verified against the API: torvalds/linux v6.0...v6.1, 250 of 10000
        # returned, last SHA == the v6.1 commit). Only an empty list leaves us
        # without a tip; then fall back to a marker that can never equal a
        # recorded head — better re-triaged than silently trusted.
        "head": (all_commits[-1].get("sha") if all_commits else "") or "unknown",
    }


def divergence_sweep(forks: list[dict]) -> tuple[list[str], int]:
    """Report every fork ahead of upstream, not just recently-pushed ones.

    Returns the Markdown lines and the count of forks that are ahead and have
    no verdict in ``TRIAGED_FORKS`` — those are what a human still has to read.
    """
    lines: list[str] = []
    fresh: list[tuple[dict, dict]] = []
    triaged: list[tuple[dict, dict]] = []
    errors: list[str] = []

    for f in forks:
        if f["full_name"] in KNOWN_FORKS:
            continue
        cmp_ = compare_to_upstream(f)
        if "_error" in cmp_:
            errors.append(f"- `{f['full_name']}` — {cmp_['_error']}")
            continue
        if cmp_["ahead"] <= 0:
            continue
        full = f["full_name"]
        # Collapse only what was reviewed *at this exact head*. A new commit
        # moves the head and puts the fork back in front of a human; a fork
        # with a verdict but no recorded head counts as unreviewed, so the
        # failure mode is "asked to look again", never "silently trusted".
        settled = full in TRIAGED_FORKS and TRIAGED_HEADS.get(full) == cmp_["head"]
        (triaged if settled else fresh).append((f, cmp_))

    fresh.sort(key=lambda pair: pair[1]["ahead"], reverse=True)
    triaged.sort(key=lambda pair: pair[1]["ahead"], reverse=True)

    lines.append("\n## Divergence sweep — every fork ahead of upstream\n")
    lines.append(
        f"{len(fresh) + len(triaged)} fork(s) carry commits upstream does not have "
        f"({len(fresh)} untriaged, {len(triaged)} already ruled on). Unlike the "
        "section above, this ignores *when* the work happened — a fork that "
        "diverged years ago and went quiet still shows up here.\n"
    )

    if fresh:
        lines.append("### Untriaged\n")
        lines.append("| Fork | ⭐ | Ahead | Behind | Last push |")
        lines.append("|------|---:|------:|-------:|-----------|")
        for f, cmp_ in fresh:
            full = f["full_name"]
            lines.append(
                f"| [`{full}`](https://github.com/{full}) | {f.get('stargazers_count', 0)} "
                f"| {cmp_['ahead']} | {cmp_['behind']} | {(f.get('pushed_at') or '')[:10]} |"
            )
        for f, cmp_ in fresh:
            full = f["full_name"]
            moved = full in TRIAGED_FORKS
            if not moved and not cmp_["commits"]:
                continue
            lines.append(f"\n#### {full}\n")
            if moved:
                # Previously ruled on, then moved — say what the old verdict was
                # so the reader only has to judge what is new. This has to come
                # before the empty-commits check: a fork whose only new commits
                # are merge noise still needs the context, and dropping it there
                # was how the promised note went missing.
                lines.append(f"> Moved since review. Earlier verdict: {TRIAGED_FORKS[full]}")
                lines.append(f"> Reviewed head was `{TRIAGED_HEADS.get(full, '(none recorded)')}`, "
                             f"now `{cmp_['head']}`.\n")
            if not cmp_["commits"]:
                lines.append("- (no commits left after filtering merge noise)")
                continue
            for c in cmp_["commits"][:8]:
                lines.append(f"- `{c['sha']}` {c['date']} — {c['message']}")
    else:
        lines.append("### Untriaged\n")
        lines.append("None — every diverging fork already has a verdict below.")

    if triaged:
        lines.append("\n<details><summary>Already triaged "
                     f"({len(triaged)})</summary>\n")
        for f, cmp_ in triaged:
            full = f["full_name"]
            lines.append(f"- `{full}` (+{cmp_['ahead']}) — {TRIAGED_FORKS[full]}")
        lines.append("\n</details>")

    if errors:
        lines.append("\n### Compare errors\n")
        lines.append(
            "These forks could not be compared, so they were **not** checked "
            "for divergence this run:\n"
        )
        lines.extend(errors)

    # Errors count as "needs a human" too: a silently unchecked fork is the
    # failure this sweep exists to prevent, and with has_activity=false the
    # workflow files no issue at all.
    return lines, len(fresh) + len(errors)


def print_heads(forks: list[dict]) -> int:
    """Emit a ready-to-paste `TRIAGED_HEADS` for every fork ahead of upstream.

    Run after reviewing a batch of forks: `--print-heads` records what you
    actually read, so later commits in those forks resurface.
    """
    rows: list[tuple[str, str]] = []
    for f in forks:
        full = f["full_name"]
        if full in KNOWN_FORKS:
            continue
        cmp_ = compare_to_upstream(f)
        if "_error" in cmp_ or cmp_["ahead"] <= 0:
            continue
        rows.append((full, cmp_["head"]))

    rows.sort()
    print("TRIAGED_HEADS: dict[str, str] = {")
    for full, head in rows:
        print(f'    "{full}": "{head}",')
    print("}")
    return 0


def main() -> int:
    if "--print-heads" in sys.argv:
        try:
            forks = list_forks(UPSTREAM)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            print(f"Could not list forks: {exc}", file=sys.stderr)
            return 1
        return print_heads(forks)

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
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        # gh_get already retried; without the fork list there is no report.
        print(f"Network error listing forks: {exc}", file=sys.stderr)
        return 1

    candidates = [
        f for f in forks
        if f["full_name"] not in KNOWN_FORKS
        and (f.get("pushed_at") or "") >= cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
    ]
    candidates.sort(key=lambda f: f.get("pushed_at") or "", reverse=True)

    if not candidates:
        print(f"No fork pushed anything new in the last {LOOKBACK_DAYS} days.",
              file=sys.stdout)
        sweep_lines, untriaged = divergence_sweep(forks)
        for line in sweep_lines:
            print(line, file=sys.stdout)
        gha_out = os.environ.get("GITHUB_OUTPUT")
        if gha_out:
            with open(gha_out, "a") as fh:
                fh.write(f"has_activity={'true' if untriaged else 'false'}\n")
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

    sweep_lines, _untriaged = divergence_sweep(forks)
    for line in sweep_lines:
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
