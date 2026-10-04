"""Smoke tests for the opentele-ng CLI."""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Integration: CLI `info` on a real synthetic tdata produced by SaveTData.
# Catches the class of regressions where the CLI imports OK but blows up at
# runtime on real data (the 1.1.0 Windows `types.auth` bug).
# ---------------------------------------------------------------------------


def _build_fixture_tdata(tmp_path):
    """Build a minimal but real tdata folder via TDesktop.SaveTData."""
    from opentele.api import API
    from opentele.td import TDesktop
    from opentele.td.account import Account
    from opentele.td.auth import AuthKey, AuthKeyType
    from opentele.td.configs import DcId

    tdesk = TDesktop()
    tdesk._TDesktop__generateLocalKey()
    base = str(tmp_path / "tdata")
    account = Account(owner=tdesk, basePath=base, api=API.TelegramDesktop, index=0)
    dc_id = DcId(2)
    user_id = 88884444
    authkey = AuthKey(b"\xab" * AuthKey.kSize, AuthKeyType.ReadFromFile, dc_id)
    account._setMtpAuthorizationCustom(dc_id, user_id, [authkey])
    tdesk._addSingleAccount(account)
    tdesk.SaveTData(base)
    return base


@pytest.fixture
def fixture_tdata_base(tmp_path):
    """Build a fixture tdata once per test using SaveTData. Narrow exception
    handling: only ImportError (e.g. tgcrypto missing) is acceptable as
    skippable; logic failures must fail the test, not silently skip."""
    try:
        return _build_fixture_tdata(tmp_path)
    except ImportError as exc:
        pytest.skip(f"fixture builder dep missing: {exc}")


def test_cli_info_on_real_fixture_tdata_succeeds(fixture_tdata_base):
    """End-to-end smoke: catches regressions like 1.1.0's `types.auth` shadow
    and `mainAccount` typo. CLI invoked as a subprocess on a tdata produced
    by ``SaveTData``. Text-mode is checked loosely (exit code + 1 anchor),
    full structural assertions live in the JSON test below."""
    res = _run(["info", fixture_tdata_base])
    assert res.returncode == 0, res.stderr
    assert "UserId=88884444" in res.stdout, res.stdout


def test_cli_info_json_on_real_fixture_tdata_parses(fixture_tdata_base):
    """JSON output is well-formed and contains the expected structural keys.
    This is the load-bearing assertion — text mode is presentation, JSON is contract."""
    res = _run(["info", fixture_tdata_base, "--json"])
    assert res.returncode == 0, res.stderr
    payload = json.loads(res.stdout)
    assert payload["accounts_count"] == 1
    assert payload["mainAccount_index"] == 0, "MainAccount → mainAccount typo regression"
    acc = payload["accounts"][0]
    assert acc["UserId"] == 88884444
    assert acc["MainDcId"] == 2
    assert acc["authKey_dcId"] == 2
    assert isinstance(acc["authKey_sha256"], str) and len(acc["authKey_sha256"]) == 64


@pytest.mark.asyncio
async def test_convert_waits_for_disconnect_future(tmp_path, monkeypatch, fixture_tdata_base):
    """Telethon returns a shielded Future; success must wait for the flush."""
    from opentele.__main__ import _convert_async
    from opentele.td import TDesktop

    output = tmp_path / "new.session"

    class Client:
        def disconnect(self):
            async def flush():
                await asyncio.sleep(0)
                output.write_bytes(b"flushed")
            return asyncio.shield(flush())

    async def convert(self, **kwargs):
        return Client()

    monkeypatch.setattr(TDesktop, "ToTelethon", convert)
    result = await _convert_async(Path(fixture_tdata_base), output, flag_use_current=True)
    assert result == 0
    assert output.read_bytes() == b"flushed"


@pytest.mark.parametrize("suffix", ["", ".session"])
def test_force_replaces_sqlite_session_without_old_account_cache(fixture_tdata_base, tmp_path, suffix):
    """Use real offline conversion and a real SQLiteSession, not a file mock."""
    from telethon import types
    from telethon.crypto import AuthKey
    from telethon.sessions import SQLiteSession

    output = tmp_path / f"account{suffix}"
    actual = tmp_path / "account.session"
    old = SQLiteSession(str(actual))
    old.auth_key = AuthKey(b"\xcd" * 256)
    old.takeout_id = 12345
    old.process_entities(types.User(id=999, access_hash=789, first_name="Old account", username="old_account"))
    old.save()
    old.close()

    assert main(["convert", fixture_tdata_base, "-o", str(output), "--use-current-session", "--force"]) == 0

    reopened = SQLiteSession(str(actual))
    try:
        assert reopened.auth_key.key == b"\xab" * 256
        assert reopened.takeout_id is None
        assert reopened.get_entity_rows_by_username("old_account") is None
    finally:
        reopened.close()
    assert not list(tmp_path.glob(".opentele-*")), "temporary sessions must be removed"


def test_failed_force_conversion_preserves_existing_session(tmp_path):
    output = tmp_path / "old.session"
    output.write_bytes(b"keep the original session")
    assert main(["convert", str(tmp_path), "-o", str(output), "--force"]) == 3
    assert output.read_bytes() == b"keep the original session"
    assert not list(tmp_path.glob(".opentele-*"))


def test_failed_conversion_does_not_leave_an_empty_output(tmp_path):
    output = tmp_path / "new.session"
    assert main(["convert", str(tmp_path), "-o", str(output)]) == 3
    assert not output.exists()
    assert not list(tmp_path.glob(".opentele-*"))


def test_conversion_does_not_replace_output_created_while_running(tmp_path, monkeypatch):
    from opentele import __main__ as cli

    output = tmp_path / "new.session"

    async def convert(tdata_path, session_path, **kwargs):
        session_path.write_bytes(b"converted")
        output.write_bytes(b"created by another process")
        return 0

    monkeypatch.setattr(cli, "_convert_async", convert)
    assert main(["convert", str(tmp_path), "-o", str(output)]) == 5
    assert output.read_bytes() == b"created by another process"
    assert not list(tmp_path.glob(".opentele-*"))


def test_conversion_missing_output_directory_exits_4(tmp_path, capsys):
    output = tmp_path / "missing" / "new.session"
    assert main(["convert", str(tmp_path), "-o", str(output)]) == 4
    assert "cannot write session file" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("race", [False, True])
def test_conversion_on_filesystem_without_hardlinks(fixture_tdata_base, tmp_path, monkeypatch, race):
    import errno

    from opentele import __main__ as cli

    output = tmp_path / "new.session"

    def unavailable(source, destination):
        if race:
            output.write_bytes(b"created by another process")
        raise OSError(errno.EOPNOTSUPP, "hard links unavailable")

    monkeypatch.setattr(cli.os, "link", unavailable)
    result = main(["convert", fixture_tdata_base, "-o", str(output), "--use-current-session"])
    assert result == (5 if race else 0)
    if race:
        assert output.read_bytes() == b"created by another process"
    else:
        from telethon.sessions import SQLiteSession
        reopened = SQLiteSession(str(output))
        try:
            assert reopened.auth_key.key == b"\xab" * 256
        finally:
            reopened.close()
    assert not list(tmp_path.glob(".opentele-*"))


def test_failed_fallback_copy_removes_partial_output(fixture_tdata_base, tmp_path, monkeypatch):
    import errno
    import shutil

    from opentele import __main__ as cli

    output = tmp_path / "new.session"

    def unavailable(*args):
        raise OSError(errno.EOPNOTSUPP, "hard links unavailable")

    def failed_copy(source, destination):
        destination.write(b"partial")
        raise OSError(errno.ENOSPC, "disk full")

    monkeypatch.setattr(cli.os, "link", unavailable)
    monkeypatch.setattr(shutil, "copyfileobj", failed_copy)
    assert main(["convert", fixture_tdata_base, "-o", str(output), "--use-current-session"]) == 4
    assert not output.exists()
    assert not list(tmp_path.glob(".opentele-*"))


@pytest.mark.asyncio
async def test_failed_disconnect_does_not_report_success(tmp_path, monkeypatch, fixture_tdata_base):
    from opentele.__main__ import _convert_async
    from opentele.td import TDesktop

    output = tmp_path / "partial.session"
    output.write_bytes(b"unflushed")

    class Client:
        async def disconnect(self):
            raise OSError("flush failed")

    async def convert(self, **kwargs):
        return Client()

    monkeypatch.setattr(TDesktop, "ToTelethon", convert)
    assert await _convert_async(Path(fixture_tdata_base), output, flag_use_current=True) == 4


@pytest.mark.asyncio
async def test_empty_session_is_not_published(tmp_path, monkeypatch, fixture_tdata_base):
    from opentele.__main__ import _convert_async
    from opentele.td import TDesktop

    output = tmp_path / "empty.session"
    output.touch()

    class Client:
        def disconnect(self):
            return None

    async def convert(self, **kwargs):
        return Client()

    monkeypatch.setattr(TDesktop, "ToTelethon", convert)
    assert await _convert_async(Path(fixture_tdata_base), output, flag_use_current=True) == 4
