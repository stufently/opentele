"""Smoke tests for the opentele-ng CLI."""
import json
import subprocess
import sys

import pytest

from opentele.__main__ import build_parser, main


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "opentele", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_version_flag_prints_version():
    res = _run(["--version"])
    assert res.returncode == 0
    assert "opentele-ng" in res.stdout
    from opentele import __version__
    assert __version__ in res.stdout


def test_cli_help_lists_subcommands():
    res = _run(["--help"])
    assert res.returncode == 0
    assert "info" in res.stdout
    assert "convert" in res.stdout


def test_cli_no_args_exits_nonzero():
    res = _run([])
    assert res.returncode != 0


def test_cli_info_missing_path_exits_2():
    res = _run(["info", "/nonexistent/tdata/path/zzz"])
    assert res.returncode == 2
    assert "not a directory" in res.stderr


def test_cli_convert_missing_path_exits_2(tmp_path):
    out = tmp_path / "out.session"
    res = _run(["convert", "/nonexistent/tdata/zzz", "-o", str(out)])
    assert res.returncode == 2


def test_cli_convert_refuses_overwrite_without_force(tmp_path):
    out = tmp_path / "exists.session"
    out.write_bytes(b"dummy")
    # Use an existing dir as tdata so we hit the overwrite check before TDesktop loads.
    res = _run(["convert", str(tmp_path), "-o", str(out)])
    assert res.returncode == 5
    assert "force" in res.stderr.lower()


def test_cli_convert_refuses_overwrite_without_suffix(tmp_path):
    """Telethon appends `.session`; --force gate must catch both forms."""
    suffixed = tmp_path / "x.session"
    suffixed.write_bytes(b"dummy")
    res = _run(["convert", str(tmp_path), "-o", str(tmp_path / "x")])
    assert res.returncode == 5, res.stderr
    assert "force" in res.stderr.lower()


def test_cli_info_existing_dir_but_not_tdata_exits_3(tmp_path):
    """Existing directory that's not actually a tdata folder should exit 3, not crash."""
    res = _run(["info", str(tmp_path)])
    assert res.returncode == 3, res.stderr
    assert "failed to load" in res.stderr.lower()


def test_build_parser_returns_argparse():
    parser = build_parser()
    # info subparser
    args = parser.parse_args(["info", "/tmp/example"])
    assert args.command == "info"
    assert args.tdata == "/tmp/example"
    # convert subparser
    args = parser.parse_args(["convert", "/tmp/in", "-o", "/tmp/out.session"])
    assert args.command == "convert"
    assert args.use_current_session is False
    assert args.force is False


def test_main_with_help_arg_raises_systemexit():
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_telethon_module_has_types_namespace():
    """Regression: user-reported Windows bug — `from .configs import *` star-import
    was failing to surface `types` in some envs, so `types.auth.LoginTokenSuccess`
    in QR-login crashed with AttributeError. Now `from telethon import types`
    is explicit at the top of src/tl/telethon.py."""
    from opentele.tl import telethon as tl_module
    assert hasattr(tl_module, "types"), \
        "telethon namespace `types` must be importable in src/tl/telethon.py"
    assert hasattr(tl_module.types, "auth"), \
        "types.auth must resolve to telethon.types.auth (not stdlib types)"


def test_ensure_utf8_stdout_does_not_crash_when_unavailable():
    """Regression: Windows cp1251 console crashed CLI info output on `└─`.
    _ensure_utf8_stdout should tolerate streams without `reconfigure`."""
    import io

    from opentele.__main__ import _ensure_utf8_stdout
    saved = sys.stdout
    try:
        sys.stdout = io.StringIO()  # no .reconfigure()
        _ensure_utf8_stdout()       # must not raise
    finally:
        sys.stdout = saved
