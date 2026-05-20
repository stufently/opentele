"""Rewrite src/devices.py to load device_models lists from src/devices.json
instead of carrying them as Python literals.

Keeps system_versions lists inline (they're small + carry inline TDesktop
version comments worth preserving). Only device_models — the huge ones —
move to JSON.

Idempotent: re-running on an already-slim devices.py is a no-op.

Usage:
    python scripts/slim_devices_py.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


DEVICES_PY = Path(__file__).resolve().parent.parent / "src" / "devices.py"


def find_block(lines: list[str], start_marker: str, list_attr: str) -> tuple[int, int] | None:
    """Locate `device_models = [...]` block for a class whose definition contains
    `start_marker`. Returns (first_line_idx_of_class, end_line_idx_inclusive_of_]).
    """
    in_class = False
    for i, line in enumerate(lines):
        if line.startswith("class ") and start_marker in line:
            in_class = True
            continue
        if in_class and line.startswith("class "):  # next class — stop searching
            return None
        if in_class:
            stripped = line.lstrip()
            if stripped.startswith(f"{list_attr} = ["):
                # Find the matching closing bracket — first line that starts with `    ]`.
                indent = len(line) - len(line.lstrip())
                close_pattern = " " * indent + "]"
                for j in range(i + 1, len(lines)):
                    if lines[j].rstrip() == close_pattern:
                        return (i, j)
                raise RuntimeError(f"unterminated {list_attr} in {start_marker}")
    return None


def rewrite() -> int:
    text = DEVICES_PY.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    # If we've already migrated, the loader is present — bail.
    if "_DATA = _load_devices_json()" in text:
        print("devices.py already migrated, nothing to do")
        return 0

    # Blocks to swap, ordered top→bottom (so line indices stay valid if we go
    # bottom→top).
    blocks = [
        ("class iOSDevice", "device_models", "ios"),
        ("class AndroidDevice", "device_models", "android"),
        ("class macOSDevice", "device_models", "macos"),
        ("class GeneralDesktopDevice", "device_models", "desktop"),
    ]

    # Walk bottom→top so earlier replacements don't shift later line numbers.
    for class_marker, attr, json_key in blocks:
        loc = find_block(lines, class_marker, attr)
        if loc is None:
            raise RuntimeError(f"could not locate {attr} block in {class_marker}")
        i, j = loc
        first_line = lines[i]
        indent = " " * (len(first_line) - len(first_line.lstrip()))
        # Compose replacement:
        replacement = (
            f'{indent}# device_models loaded from devices.json — see '
            f'scripts/extract_devices_data.py for the source of truth.\n'
            f'{indent}device_models: List[str] = _DATA["{json_key}"]["device_models"]\n'
        )
        lines[i:j + 1] = [replacement]

    # Insert the JSON loader near the top of the module, right after the
    # existing imports + `_T = TypeVar(...)` line.
    loader_block = (
        "\n"
        "# --- devices.json loader ------------------------------------------------\n"
        "# Phase 1.2.2: device_models lists moved out of this file (was 174 KB of\n"
        "# Python literals) into a single JSON blob shipped alongside as package\n"
        "# data. Loaded once on import, cached in `_DATA`. Refresh via\n"
        "#   `python scripts/extract_devices_data.py`.\n"
        "import json as _json\n"
        "from pathlib import Path as _Path\n"
        "\n"
        "def _load_devices_json() -> dict:\n"
        "    p = _Path(__file__).resolve().parent / \"devices.json\"\n"
        "    with p.open(encoding=\"utf-8\") as fh:\n"
        "        return _json.load(fh)\n"
        "\n"
        "_DATA = _load_devices_json()\n"
    )

    # Insert after the `_T = TypeVar("_T")` line.
    for idx, line in enumerate(lines):
        if line.startswith("_T = TypeVar"):
            lines.insert(idx + 1, loader_block)
            break
    else:
        raise RuntimeError("could not find _T = TypeVar(...) anchor")

    DEVICES_PY.write_text("".join(lines), encoding="utf-8")
    print(f"rewrote {DEVICES_PY} ({DEVICES_PY.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(rewrite())
