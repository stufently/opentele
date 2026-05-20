#!/usr/bin/env bash
# opentele-ng — PyPI publish helper (Docker-based).
#
# Reads PYPI_API_TOKEN (or TEST_PYPI_API_TOKEN with --test) from .env in the
# repo root. Builds a sdist + wheel inside a digest-pinned python:3.14-slim
# container (see IMG variable below), runs `twine check`, then uploads via
# `twine upload`.
#
# Usage:
#   scripts/publish.sh           # → publish to https://pypi.org
#   scripts/publish.sh --test    # → publish to https://test.pypi.org
#   scripts/publish.sh --dry-run # → build only, no upload
#
# Requires:  docker
set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT=$(pwd)

# --- parse flags ------------------------------------------------------------
target_repo="pypi"
target_url="https://upload.pypi.org/legacy/"
token_var="PYPI_API_TOKEN"
dry_run=0

for arg in "$@"; do
    case "$arg" in
        --test)
            target_repo="testpypi"
            target_url="https://test.pypi.org/legacy/"
            token_var="TEST_PYPI_API_TOKEN"
            ;;
        --dry-run)
            dry_run=1
            ;;
        -h|--help)
            sed -n '2,13p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg" >&2
            exit 1
            ;;
    esac
done

# --- load secrets (only when actually uploading) ----------------------------
token=""
if [[ $dry_run -eq 0 ]]; then
    if [[ ! -f "$REPO_ROOT/.env" ]]; then
        echo "ERROR: $REPO_ROOT/.env not found. Copy .env.example and fill in $token_var." >&2
        exit 1
    fi
    # Source .env WITHOUT `set -a` — variables stay as shell-local, not exported
    # to child processes' environments (so docker subprocesses don't inherit them,
    # and they don't appear in /proc/<pid>/environ for the parent shell either).
    # shellcheck source=/dev/null
    source "$REPO_ROOT/.env"
    token="${!token_var:-}"
    if [[ -z "$token" ]]; then
        echo "ERROR: $token_var is empty in .env." >&2
        exit 1
    fi
fi

# Pinned digest for reproducible builds. Refresh manually via:
#   docker pull python:3.14-slim && docker inspect python:3.14-slim --format='{{index .RepoDigests 0}}'
IMG="python:3.14-slim@sha256:a7185a8e40af01bf891414a4df16ef10fc6000cee460a404a13da9029fe41604"

echo "==> Cleaning build artifacts"
rm -rf build/ dist/ ./*.egg-info/

# Compose the in-container script
build_step='set -e
cd /work
pip install --quiet --upgrade build twine
python -m build
ls -la dist/
python -m twine check dist/*'

echo "==> Building (sdist + wheel) inside $IMG"
docker run --rm \
    -v "$REPO_ROOT:/work" \
    -w /work \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    "$IMG" bash -c "$build_step"

if [[ $dry_run -eq 1 ]]; then
    echo
    echo "==> --dry-run: skipping upload."
    echo "Artifacts:"
    ls -la dist/
    exit 0
fi

echo
echo "==> Uploading to $target_repo ($target_url)"
# Pass token via host env var (not argv) so it doesn't show in `ps` output.
TWINE_PASSWORD="$token" docker run --rm \
    -v "$REPO_ROOT:/work" \
    -w /work \
    --user "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    -e TWINE_USERNAME=__token__ \
    -e TWINE_PASSWORD \
    -e TWINE_REPOSITORY_URL="$target_url" \
    "$IMG" bash -c '
        set -e
        pip install --quiet --upgrade twine
        python -m twine upload --non-interactive dist/*
    '

echo
echo "==> Done. Verify at:"
if [[ "$target_repo" = "pypi" ]]; then
    echo "    https://pypi.org/project/opentele-ng/"
else
    echo "    https://test.pypi.org/project/opentele-ng/"
fi
