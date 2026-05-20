# Docker

`opentele-ng` is published as a multi-arch container at **`ghcr.io/stufently/opentele-ng`** (linux/amd64 + linux/arm64). The image is ~140 MB, runs as a non-root user, and has `opentele-ng` as its entrypoint — so the same flags work directly.

Pull:

```bash
docker pull ghcr.io/stufently/opentele-ng:latest
```

Tags:

| Tag                 | What it means                                                                 |
| ------------------- | ----------------------------------------------------------------------------- |
| `:latest`           | Most recent semver release (e.g. `1.2.0`). What you want in production.       |
| `:1.2.0`            | Pinned exact version.                                                          |
| `:1.2`, `:1`        | Pinned major / minor. Rolls forward inside that line on new releases.          |
| `:main`             | Tip of `main`. Use only for debugging; can break between commits.              |
| `:sha-abcdef0`      | Exact commit. Useful for CI pipelines that want byte-identical reproducibility. |

## Inspect a tdata folder

Mount your tdata read-only and run `info`:

```bash
docker run --rm \
    -v "/path/to/Telegram/tdata:/tdata:ro" \
    ghcr.io/stufently/opentele-ng:latest \
    info /tdata
```

`--json` for machine-readable output:

```bash
docker run --rm \
    -v "/path/to/Telegram/tdata:/tdata:ro" \
    ghcr.io/stufently/opentele-ng:latest \
    info /tdata --json | jq '.accounts[].UserId'
```

## Convert tdata → Telethon `.session`

You need two mounts: tdata (read-only) and an output directory the container can write to.

```bash
mkdir -p ./out
docker run --rm \
    -v "/path/to/Telegram/tdata:/tdata:ro" \
    -v "$PWD/out:/out" \
    ghcr.io/stufently/opentele-ng:latest \
    convert /tdata --output /out/me.session
```

The image runs as **UID/GID `10001:10001`** inside the container. On Linux hosts you may need to chown the output dir, or mount with `--user "$(id -u):$(id -g)"` to write as your own user:

```bash
docker run --rm \
    --user "$(id -u):$(id -g)" \
    -v "/path/to/Telegram/tdata:/tdata:ro" \
    -v "$PWD/out:/out" \
    ghcr.io/stufently/opentele-ng:latest \
    convert /tdata --output /out/me.session
```

## Batch in a shell loop

```bash
for tdata in /backup/Telegram*/tdata; do
    name=$(basename "$(dirname "$tdata")")
    docker run --rm \
        -v "$tdata:/tdata:ro" \
        -v "$PWD/out:/out" \
        --user "$(id -u):$(id -g)" \
        ghcr.io/stufently/opentele-ng:latest \
        info /tdata --json > "out/$name.json"
done
```

This stays read-only (no network, no `convert`), so it's safe to parallelize with `xargs -P` if you have hundreds of folders.

## Build the image from source

Useful when you want to test changes before merging:

```bash
git clone https://github.com/stufently/opentele
cd opentele
docker build -t opentele-ng:dev .
docker run --rm opentele-ng:dev --version
```

The `Dockerfile` is multi-stage (build wheel → install in slim final image), pinned to `python:3.13-slim`, runs as a non-root user `app`. End image is the same one published to GHCR — only the registry / tagging differs.

## Air-gapped / offline

The image is fully self-contained — no `pip install` happens at runtime. After `docker pull` once on a connected host, you can `docker save` and ship the tar:

```bash
docker pull ghcr.io/stufently/opentele-ng:latest
docker save ghcr.io/stufently/opentele-ng:latest | gzip > opentele-ng.tar.gz

# on the air-gapped host:
gunzip -c opentele-ng.tar.gz | docker load
docker run --rm ghcr.io/stufently/opentele-ng:latest --version
```

## Verifying provenance

Releases tagged `v*` are signed with [Sigstore](https://www.sigstore.dev/) attestations both on PyPI (PEP 740) and on the GHCR image (provenance + SBOM). To verify the image:

```bash
# Requires gh CLI.
gh attestation verify oci://ghcr.io/stufently/opentele-ng:1.2.0 \
    --repo stufently/opentele
```
