# opentele-ng — production image.
#
# Multi-stage: builds from the local source tree (so the image always matches
# the commit), produces a final slim image with only opentele-ng + runtime deps.
# No Qt — that's the whole point.
#
# Usage:
#   docker run --rm -v "/path/to/Telegram/tdata:/tdata:ro" \
#       ghcr.io/stufently/opentele-ng:latest info /tdata
#
#   docker run --rm \
#       -v "/path/to/Telegram/tdata:/tdata:ro" \
#       -v "$PWD/out:/out" \
#       ghcr.io/stufently/opentele-ng:latest convert /tdata --output /out/me.session
ARG PYTHON_VERSION=3.13
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /build
# MANIFEST.in `include`s these — copy them in so sdist build doesn't warn.
COPY pyproject.toml MANIFEST.in requirements.txt README.md LICENSE CHANGELOG.md ACKNOWLEDGMENTS.md SECURITY.md ./
COPY src/ ./src/
COPY docs/examples/ ./docs/examples/

RUN pip install --no-cache-dir --upgrade pip build && \
    python -m build --wheel --outdir /wheels

# --- final image ---------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim

LABEL org.opencontainers.image.title="opentele-ng" \
      org.opencontainers.image.description="Modern fork of opentele for Python 3.10-3.14 (no Qt runtime). Convert Telegram Desktop tdata to Telethon sessions." \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/stufently/opentele" \
      org.opencontainers.image.documentation="https://stufently.github.io/opentele/"

# Non-root user for safer mounts. UID/GID pinned so the docs can promise
# a stable mapping for `-v` mounts.
ARG APP_UID=10001
ARG APP_GID=10001
RUN groupadd -g ${APP_GID} app && \
    useradd -u ${APP_UID} -g ${APP_GID} -d /home/app -m -s /sbin/nologin app

COPY --from=builder /wheels/*.whl /tmp/

RUN pip install --no-cache-dir /tmp/opentele_ng-*.whl && \
    rm -rf /tmp/opentele_ng-*.whl

USER app
WORKDIR /home/app

ENTRYPOINT ["opentele-ng"]
CMD ["--help"]
