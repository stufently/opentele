"""CLI for opentele-ng.

Three subcommands:

    opentele-ng info     <tdata>                 — print accounts metadata (read-only)
    opentele-ng convert  <tdata> <session.session> — convert tdata → Telethon session file
    opentele-ng --version

Designed to cover the 80% case in one shell command without writing Python.
The CLI is intentionally thin — it delegates to opentele.td.TDesktop and
opentele.tl.TelegramClient. No new wire-format code lives here.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__


def _sha256_hex(b: bytes | bytearray | memoryview | None) -> str | None:
    if b is None:
        return None
    return hashlib.sha256(bytes(b)).hexdigest()


def _account_summary(account: Any, idx: int) -> dict[str, Any]:
    info: dict[str, Any] = {"index": idx}
    for attr in ("UserId", "MainDcId"):
        try:
            v = getattr(account, attr)
            if not callable(v) and v is not None:
                info[attr] = v
        except Exception:
            pass
    try:
        ak = getattr(account, "authKey", None)
        if ak is not None:
            key_bytes = bytes(getattr(ak, "key", b"") or b"")
            info["authKey_sha256"] = _sha256_hex(key_bytes)
            info["authKey_dcId"] = int(getattr(ak, "dcId", 0) or 0)
    except Exception as exc:
        info["authKey_error"] = repr(exc)
    return info


def cmd_info(args: argparse.Namespace) -> int:
    from .exception import OpenTeleException
    from .td import TDesktop

    tdata_path = Path(args.tdata).expanduser().resolve()
    if not tdata_path.is_dir():
        print(f"error: tdata path is not a directory: {tdata_path}", file=sys.stderr)
        return 2

    try:
        td = TDesktop(str(tdata_path))
    except OpenTeleException as exc:
        print(f"error: TDesktop failed to load tdata at {tdata_path}: {exc}", file=sys.stderr)
        return 3
    if not td.isLoaded():
        print(f"error: TDesktop failed to load tdata at {tdata_path}", file=sys.stderr)
        return 3

    accounts = list(td.accounts) if hasattr(td, "accounts") else []
    main_idx = getattr(getattr(td, "mainAccount", None), "index", None)
    out = {
        "tdata_path": str(tdata_path),
        "AppVersion": getattr(td, "AppVersion", None),
        "mainAccount_index": main_idx,
        "accounts_count": len(accounts),
        "accounts": [_account_summary(a, i) for i, a in enumerate(accounts)],
    }

    if args.json:
        print(json.dumps(out, indent=2, sort_keys=True, default=repr))
    else:
        print(f"tdata: {out['tdata_path']}")
        print(f"  AppVersion:       {out['AppVersion']}")
        print(f"  accounts:         {out['accounts_count']}")
        print(f"  main account idx: {out['mainAccount_index']}")
        for acc in out["accounts"]:
            print(f"  └─ [{acc['index']}] UserId={acc.get('UserId')} "
                  f"DC={acc.get('MainDcId')} "
                  f"authKey_sha256={(acc.get('authKey_sha256') or '')[:16]}…")
    return 0


def _normalize_session_path(p: Path) -> Path:
    """Replicate Telethon's SQLiteSession suffix behavior so `--force` is reliable."""
    return p if p.suffix == ".session" else p.with_suffix(p.suffix + ".session")


async def _convert_async(tdata_path: Path, session_path: Path, *, flag_use_current: bool) -> int:
    from .api import API, CreateNewSession, UseCurrentSession
    from .exception import OpenTeleException
    from .td import TDesktop

    try:
        td = TDesktop(str(tdata_path))
    except OpenTeleException as exc:
        print(f"error: TDesktop failed to load tdata at {tdata_path}: {exc}", file=sys.stderr)
        return 3
    if not td.isLoaded():
        print(f"error: TDesktop failed to load tdata at {tdata_path}", file=sys.stderr)
        return 3

    flag = UseCurrentSession if flag_use_current else CreateNewSession
    client = await td.ToTelethon(
        session=str(session_path),
        flag=flag,
        api=API.TelegramDesktop.Generate(),
    )
    try:
        # Disconnect so the .session file is flushed to disk cleanly.
        if hasattr(client, "disconnect"):
            res = client.disconnect()
            if asyncio.iscoroutine(res):
                await res
    except Exception:
        pass

    if not session_path.exists():
        # Telethon appends `.session`; tolerate both.
        alt = session_path.with_suffix(session_path.suffix + ".session") if session_path.suffix != ".session" else session_path
        if alt.exists():
            session_path = alt
        else:
            print(f"error: session file was not created at {session_path}", file=sys.stderr)
            return 4
    print(f"ok: wrote session file → {session_path}")
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    tdata_path = Path(args.tdata).expanduser().resolve()
    session_path = Path(args.output).expanduser().resolve()
    # Telethon will write to `<output>.session` even if `--output` lacks the suffix —
    # check both forms before clobbering anything.
    suffixed_path = _normalize_session_path(session_path)

    if not tdata_path.is_dir():
        print(f"error: tdata path is not a directory: {tdata_path}", file=sys.stderr)
        return 2
    if not args.force:
        for candidate in {session_path, suffixed_path}:
            if candidate.exists():
                print(
                    f"error: refusing to overwrite existing {candidate}; pass --force to override",
                    file=sys.stderr,
                )
                return 5

    return asyncio.run(
        _convert_async(tdata_path, session_path, flag_use_current=args.use_current_session)
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="opentele-ng",
        description="Convert / inspect Telegram Desktop tdata folders without Qt.",
    )
    p.add_argument("--version", action="version", version=f"opentele-ng {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="Print accounts metadata for a tdata folder (read-only).")
    p_info.add_argument("tdata", help="Path to a Telegram Desktop tdata folder.")
    p_info.add_argument("--json", action="store_true", help="Emit JSON instead of human-friendly text.")
    p_info.set_defaults(func=cmd_info)

    p_conv = sub.add_parser("convert", help="Convert a tdata folder to a Telethon .session file.")
    p_conv.add_argument("tdata", help="Path to a Telegram Desktop tdata folder.")
    p_conv.add_argument("-o", "--output", required=True, help="Output .session file path.")
    p_conv.add_argument(
        "--use-current-session",
        action="store_true",
        help="Reuse the current Telegram session (default: create a new one).",
    )
    p_conv.add_argument("--force", action="store_true", help="Overwrite existing output file.")
    p_conv.set_defaults(func=cmd_convert)

    return p


def _ensure_utf8_stdout() -> None:
    """Windows consoles default to cp1251/cp437 which can't render the box-drawing
    glyphs (└─) we use in the info output. Try to upgrade stdout to UTF-8."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    _ensure_utf8_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
