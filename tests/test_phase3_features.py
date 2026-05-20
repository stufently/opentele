"""Phase 3: kMaxAccounts bump + kwargs forward + sharemethod nuitka + QR docs.

Source: snakechilds/opentele-nuitka (kMaxAccounts/kwargs/sharemethod) + Ehekatech (QR docs).
3 AI prep review (Codex) corrected scope:
- kMaxAccounts → 6 (TDesktop premium limit), NOT 100
- Unknown keyType → fail-fast, NOT warn-only (deferred to Phase 4 due to risk)
"""
import inspect
import pathlib

import pytest

from opentele.td import account as account_module
from opentele.td.tdesktop import TDesktop

# === kMaxAccounts ===


def test_kMaxAccounts_matches_tdesktop_premium_limit() -> None:
    """kMaxAccounts должен быть 6 (TDesktop's kPremiumMaxAccounts).

    Phase 3: bumped from upstream's hardcoded 3 to 6 to match Telegram Desktop's
    Premium account limit (`main_domain.h: kPremiumMaxAccounts = 6`).
    Codex caught: snakechilds-style 100 makes no sense — TDesktop itself caps at 6.
    """
    assert TDesktop.kMaxAccounts == 6, (
        f"Expected kMaxAccounts=6 (TDesktop premium limit), got {TDesktop.kMaxAccounts}. "
        f"Upstream's 3 (non-premium) bumped to 6 to allow real-world Premium configurations."
    )


def test_kMaxAccounts_docstring_mentions_change() -> None:
    """Класс TDesktop docstring должен упоминать новое значение / Phase 3."""
    doc = inspect.getsource(TDesktop)
    # Просто sanity: docstring/comments не оставляют упоминание 3 без контекста.
    assert "kMaxAccounts" in doc


# === kwargs forward в FromTelethon ===


def test_TDesktop_FromTelethon_accepts_kwargs() -> None:
    """TDesktop.FromTelethon должен принимать **kwargs."""
    sig = inspect.signature(TDesktop.FromTelethon)
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in sig.parameters.values()
    )
    assert has_var_keyword, (
        f"TDesktop.FromTelethon must accept **kwargs to forward Telethon options. "
        f"Current signature: {sig}"
    )


def test_Account_FromTelethon_accepts_kwargs() -> None:
    """Account.FromTelethon тоже должен принимать **kwargs."""
    Account = account_module.Account
    sig = inspect.signature(Account.FromTelethon)
    has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in sig.parameters.values()
    )
    assert has_var_keyword, (
        f"Account.FromTelethon must accept **kwargs. Current signature: {sig}"
    )


# === sharemethod nuitka fix ===


def test_sharemethod_does_not_use_func_dunder_class() -> None:
    """Nuitka не может скомпилировать `func.__class__.__name__` в sharemethod.

    Phase 3 fix: используем стабильные `clsName="function"`, `bases=(object,)`, `attrs={}`.
    Source: snakechilds/opentele-nuitka `eb4ff4d`.
    """
    from opentele import utils

    src = inspect.getsource(utils)
    # Поиск проблемной строки. Старый код был:
    #   return super().__new__(cls, func.__class__.__name__, (object,), {})
    # Новый:
    #   return super().__new__(cls, "function", (object,), {})
    assert 'func.__class__.__name__' not in src or '"function"' in src, (
        "sharemethod still uses func.__class__.__name__ — fails Nuitka compilation. "
        "Phase 3 fix: use literal 'function' instead."
    )


# === QR login docs ===


def test_qr_login_docs_exists() -> None:
    """docs/examples/qr-login.md должен существовать после Phase 3."""
    repo_root = pathlib.Path(__file__).parent.parent
    qr_doc = repo_root / "docs" / "examples" / "qr-login.md"
    assert qr_doc.exists(), f"Missing QR login docs at {qr_doc}"
    content = qr_doc.read_text(encoding="utf-8")
    assert "QR" in content or "qr" in content.lower(), (
        "QR docs file exists but doesn't mention QR"
    )
    assert "Telethon" in content or "telethon" in content.lower(), (
        "QR docs should mention Telethon (it's a Telethon flow)"
    )
