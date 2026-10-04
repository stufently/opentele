"""Check official stable releases even when the fork network is quiet.

Uses only the standard library; the scheduled workflow need not install the
runtime dependencies. Read the Desktop layer table as data, without importing
opentele or executing its source. Network or payload errors request attention.
"""
from __future__ import annotations

import ast
import json
import os
import re
import urllib.request
from http.client import HTTPException
from pathlib import Path

DESKTOP_RELEASE_URL = "https://api.github.com/repos/telegramdesktop/tdesktop/releases/latest"
DESKTOP_SCHEMA_URL = (
    "https://raw.githubusercontent.com/telegramdesktop/tdesktop/{tag}/"
    "Telegram/SourceFiles/mtproto/scheme/api.tl"
)
TELETHON_RELEASE_URL = "https://pypi.org/pypi/telethon/json"
ROOT = Path(__file__).resolve().parents[1]


def fetch_text(url: str) -> str:
    headers = {"User-Agent": "opentele-ng-release-watch"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def desktop_layers(root: Path) -> dict[str, int]:
    tree = ast.parse((root / "src" / "api.py").read_text(encoding="utf-8"))
    api = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "API")
    desktop = next(
        node for node in api.body if isinstance(node, ast.ClassDef) and node.name == "TelegramDesktop"
    )
    for node in desktop.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(target, ast.Name) and target.id == "TELEGRAM_DESKTOP_LAYERS" for target in targets):
            return ast.literal_eval(node.value)
    raise ValueError("Desktop layer table missing")


def check_releases(root: Path = ROOT) -> tuple[list[str], bool]:
    lines = ["\n## Official releases watch\n"]
    attention = False
    try:
        release = json.loads(fetch_text(DESKTOP_RELEASE_URL))
        tag = release["tag_name"]
        if release["prerelease"] or release["draft"] or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
            raise ValueError("latest release is not a stable Desktop tag")
        schema = fetch_text(DESKTOP_SCHEMA_URL.format(tag=tag))
        match = re.search(r"^// LAYER (\d+)\s*$", schema, re.MULTILINE)
        if not match:
            raise ValueError("MTProto layer missing from tagged api.tl")
        layer = int(match[1])
        recorded = desktop_layers(root).get(tag[1:])
        current = recorded == layer
        attention |= not current
        status = "current" if current else f"update needed (recorded layer: {recorded})"
        lines.append(
            f"- Telegram Desktop [{tag}](https://github.com/telegramdesktop/tdesktop/releases/tag/{tag}), "
            f"layer **{layer}** — {status}."
        )
    except (OSError, HTTPException, ValueError, KeyError, TypeError, SyntaxError, StopIteration) as exc:
        attention = True
        lines.append(f"- Could not check Telegram Desktop: {exc}")

    try:
        version = json.loads(fetch_text(TELETHON_RELEASE_URL))["info"]["version"]
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("latest Telethon version is not a stable release")
        lock = (root / "requirements-docker.txt").read_text(encoding="utf-8")
        match = re.search(r"^telethon==(\d+\.\d+\.\d+)\b", lock, re.MULTILINE)
        if not match:
            raise ValueError("Telethon pin missing from Docker lock")
        locked = match[1]
        current = version == locked
        attention |= not current
        status = "current" if current else "update needed"
        lines.append(
            f"- Telethon [{version}](https://pypi.org/project/Telethon/{version}/), "
            f"Docker lock **{locked}** — {status}."
        )
    except (OSError, HTTPException, ValueError, KeyError, TypeError) as exc:
        attention = True
        lines.append(f"- Could not check Telethon: {exc}")
    return lines, attention


def main(root: Path = ROOT) -> int:
    lines, attention = check_releases(root)
    print("\n".join(lines))
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"has_activity={'true' if attention else 'false'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
