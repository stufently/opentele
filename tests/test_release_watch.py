"""Release watch must flag drift even when every fork is quiet."""
from __future__ import annotations

import importlib.util
from http.client import IncompleteRead
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_watch.py"


@pytest.fixture
def watch(tmp_path, monkeypatch):
    assert SCRIPT.exists(), "release watch has not been implemented"
    spec = importlib.util.spec_from_file_location("release_watch", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "api.py").write_text(
        'class API:\n    class TelegramDesktop:\n'
        '        TELEGRAM_DESKTOP_LAYERS = {"7.2.9": 229, "7.0.9": 228}\n'
    )
    (tmp_path / "requirements-docker.txt").write_text('telethon==1.45.0 \\\n    --hash=sha256:example\n')
    payloads = {
        module.DESKTOP_RELEASE_URL: '{"tag_name":"v7.2.9","prerelease":false,"draft":false}',
        module.TELETHON_RELEASE_URL: '{"info":{"version":"1.45.0"}}',
        module.DESKTOP_SCHEMA_URL.format(tag="v7.2.9"): '// LAYER 229\n',
    }
    monkeypatch.setattr(module, "fetch_text", lambda url: payloads[url])
    return module, tmp_path, payloads


def test_current_releases_do_not_trigger_issue(watch):
    module, root, _ = watch
    lines, attention = module.check_releases(root)
    assert not attention
    assert "7.2.9" in "\n".join(lines)
    assert "1.45.0" in "\n".join(lines)


def test_new_desktop_stable_triggers_issue(watch):
    module, root, payloads = watch
    payloads[module.DESKTOP_RELEASE_URL] = '{"tag_name":"v7.3.0","prerelease":false,"draft":false}'
    payloads[module.DESKTOP_SCHEMA_URL.format(tag="v7.3.0")] = '// LAYER 230\n'
    lines, attention = module.check_releases(root)
    assert attention
    assert "7.3.0" in "\n".join(lines)
    assert "230" in "\n".join(lines)


def test_wrong_recorded_layer_triggers_issue(watch):
    module, root, payloads = watch
    payloads[module.DESKTOP_SCHEMA_URL.format(tag="v7.2.9")] = '// LAYER 230\n'
    lines, attention = module.check_releases(root)
    assert attention
    assert "230" in "\n".join(lines)


def test_new_telethon_triggers_issue(watch):
    module, root, payloads = watch
    payloads[module.TELETHON_RELEASE_URL] = '{"info":{"version":"1.46.0"}}'
    lines, attention = module.check_releases(root)
    assert attention
    assert "1.46.0" in "\n".join(lines)


@pytest.mark.parametrize("payload", [
    '{"tag_name":"v7.2.10","prerelease":true,"draft":false}',
    '{"tag_name":"v7.3.0","prerelease":false,"draft":true}',
    '{}',
])
def test_unusable_release_payload_is_visible(watch, payload):
    module, root, payloads = watch
    payloads[module.DESKTOP_RELEASE_URL] = payload
    lines, attention = module.check_releases(root)
    assert attention
    assert "Could not check Telegram Desktop" in "\n".join(lines)
    assert "1.45.0" in "\n".join(lines), "one failure must not hide the other dependency"


@pytest.mark.parametrize("error", [TimeoutError("offline"), IncompleteRead(b"partial")])
def test_network_failure_still_checks_other_dependency(watch, monkeypatch, error):
    module, root, payloads = watch

    def fetch(url):
        if url == module.DESKTOP_RELEASE_URL:
            raise error
        return payloads[url]

    monkeypatch.setattr(module, "fetch_text", fetch)
    lines, attention = module.check_releases(root)
    assert attention
    assert "Could not check Telegram Desktop" in "\n".join(lines)
    assert "1.45.0" in "\n".join(lines)


def test_missing_schema_layer_is_not_silently_current(watch):
    module, root, payloads = watch
    payloads[module.DESKTOP_SCHEMA_URL.format(tag="v7.2.9")] = 'not a schema'
    lines, attention = module.check_releases(root)
    assert attention
    assert "Could not check Telegram Desktop" in "\n".join(lines)


@pytest.mark.parametrize("version,expected", [("1.45.0", "false"), ("1.46.0", "true")])
def test_cli_sets_workflow_attention_output(watch, monkeypatch, capsys, version, expected):
    module, root, payloads = watch
    payloads[module.TELETHON_RELEASE_URL] = '{"info":{"version":"' + version + '"}}'
    output = root / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert module.main(root) == 0
    assert output.read_text() == f"has_activity={expected}\n"
    assert version in capsys.readouterr().out
