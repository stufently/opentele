# CLI quick start

`opentele-ng` ships a small CLI for the common one-shot workflows. After `pip install opentele-ng`, the `opentele-ng` command is on your `PATH`.

## Inspect a tdata folder (read-only)

```bash
opentele-ng info /path/to/Telegram/tdata
```

```
tdata: /path/to/Telegram/tdata
  AppVersion:       6008002
  accounts:         2
  main account idx: 0
  └─ [0] UserId=6925730240 DC=4 authKey_sha256=775161c1b987143b…
  └─ [1] UserId=8001234567 DC=5 authKey_sha256=eac0a1a2cc10a5ce…
```

Add `--json` to get a machine-readable dump (suitable for piping into `jq` or saving alongside other metadata):

```bash
opentele-ng info /path/to/Telegram/tdata --json | jq '.accounts[].UserId'
```

## Convert tdata → Telethon `.session` file

```bash
opentele-ng convert /path/to/Telegram/tdata --output ./me.session
```

By default this **creates a new Telegram session** (Telegram Desktop's existing session keeps working separately). Pass `--use-current-session` to reuse the live session instead:

```bash
opentele-ng convert /path/to/Telegram/tdata \
    --output ./me.session \
    --use-current-session
```

Add `--force` to overwrite an existing output file.

## Exit codes

| Code | Meaning                                                |
| ---: | ------------------------------------------------------ |
|    0 | Success.                                               |
|    2 | The tdata path is not a directory / does not exist.    |
|    3 | `TDesktop` failed to load (corrupt tdata, wrong path). |
|    4 | Telethon did not produce the `.session` file.          |
|    5 | Output file exists; rerun with `--force`.              |
|  130 | Interrupted (Ctrl-C).                                  |

## Scripting

The CLI is the right tool when you don't need to customise anything. As soon as you want to set a custom API ID, pass extra Telethon options, or do batch operations, switch to the Python API — see [`convert-tdata-to-telethon.md`](convert-tdata-to-telethon.md).
