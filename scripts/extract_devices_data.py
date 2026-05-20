"""One-shot: dump device tables from src/devices.py to src/devices.json.

Reads the current devices.py module (after the comma fix in line 5333) and
serializes each class's `device_models` + `system_versions` lists into a
single JSON file. Re-running this script is safe — it produces the same
bytes given the same input.

Usage:
    docker run --rm -v "$PWD:/work" -w /work python:3.14-slim \\
        bash -c 'pip install -q -e . && python scripts/extract_devices_data.py'

Output: src/devices.json (commit alongside the slimmed devices.py).
"""
from __future__ import annotations

import json
from pathlib import Path


def main() -> int:
    from opentele import devices as d

    payload = {
        "_comment": (
            "Auto-extracted from src/devices.py. Regenerate via "
            "scripts/extract_devices_data.py. Do not hand-edit unless you "
            "also update the script that produced these values."
        ),
        "desktop": {
            "device_models": list(d.GeneralDesktopDevice.device_models),
        },
        "macos": {
            "device_models": list(d.macOSDevice.device_models),
            "system_versions": list(d.macOSDevice.system_versions),
        },
        "android": {
            "device_models": list(d.AndroidDevice.device_models),
            "system_versions": list(d.AndroidDevice.system_versions),
        },
        "ios": {
            "device_models": list(d.iOSDevice.device_models),
            "system_versions": list(d.iOSDevice.system_versions),
        },
    }

    out = Path(__file__).resolve().parent.parent / "src" / "devices.json"
    out.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    sizes = {
        k: (len(v["device_models"]) if "device_models" in v else None)
        for k, v in payload.items() if isinstance(v, dict)
    }
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
    print(f"counts: {sizes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
