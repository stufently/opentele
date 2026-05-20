#!/usr/bin/env bash
# opentele-ng — PyPI publish helper.
#
# Reads PYPI_API_TOKEN (or TEST_PYPI_API_TOKEN with --test) from .env in the
# repo root. Builds a sdist + wheel via `python -m build` and uploads via
# `twine upload`.
#
# Usage:
#   scripts/publish.sh           # → publish to https://pypi.org
#   scripts/publish.sh --test    # → publish to https://test.pypi.org
#   scripts/publish.sh --dry-run # → build only, no upload
#
# Requires:  python -m pip install build twine
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT=$(pwd)

# --- load secrets -----------------------------------------------------------
if [[ ! -f "$REPO_ROOT/.env" ]]; then
    echo "ERROR: $REPO_ROOT/.env not found. Copy .env.example and fill in PYPI_API_TOKEN." >&2
    exit 1
fi

set -a
# shellcheck source=/dev/null
source "$REPO_ROOT/.env"
set +a

# --- parse flags ------------------------------------------------------------
target_repo="pypi"
target_url="https://upload.pypi.org/legacy/"
token="${PYPI_API_TOKEN:-}"
dry_run=0

for arg in "$@"; do
    case "$arg" in
        --test)
            target_repo="testpypi"
            target_url="https://test.pypi.org/legacy/"
            token="${TEST_PYPI_API_TOKEN:-}"
            ;;
        --dry-run)
            dry_run=1
            ;;
        -h|--help)
            sed -n '2,12p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg" >&2
            exit 1
            ;;
    esac
done

if [[ $dry_run -eq 0 && -z "$token" ]]; then
    echo "ERROR: token for $target_repo is empty in .env. Fill PYPI_API_TOKEN (or TEST_PYPI_API_TOKEN with --test)." >&2
    exit 1
fi

# --- pre-flight: clean stale builds ----------------------------------------
echo "==> Cleaning build artifacts"
rm -rf build/ dist/ ./*.egg-info/

# --- pre-flight: install build deps ----------------------------------------
echo "==> Ensuring build + twine present"
python -m pip install --quiet --upgrade build twine

# --- build ------------------------------------------------------------------
echo "==> Building sdist + wheel"
python -m build

echo
echo "==> Artifacts:"
ls -la dist/

# --- check ------------------------------------------------------------------
echo
echo "==> twine check"
python -m twine check dist/*

# --- upload -----------------------------------------------------------------
if [[ $dry_run -eq 1 ]]; then
    echo
    echo "==> --dry-run: skipping upload."
    exit 0
fi

echo
echo "==> Uploading to $target_repo ($target_url)"
TWINE_USERNAME=__token__ \
TWINE_PASSWORD="$token" \
TWINE_REPOSITORY_URL="$target_url" \
    python -m twine upload --non-interactive dist/*

echo
echo "==> Done. Verify at:"
if [[ "$target_repo" = "pypi" ]]; then
    echo "    https://pypi.org/project/opentele-ng/"
else
    echo "    https://test.pypi.org/project/opentele-ng/"
fi
