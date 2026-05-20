# Batch-convert many tdata folders

If you have a directory full of `tdata` folders (one per Telegram account, say from a backup tool), you can convert them in parallel via the Python API.

```python
import asyncio
from pathlib import Path
from opentele.api import API, CreateNewSession
from opentele.td import TDesktop


async def convert_one(tdata: Path, sessions_dir: Path) -> tuple[Path, bool, str]:
    session_path = sessions_dir / f"{tdata.parent.name}.session"
    if session_path.exists():
        return session_path, False, "already exists"
    try:
        td = TDesktop(str(tdata))
        if not td.isLoaded():
            return session_path, False, "tdata failed to load"
        client = await td.ToTelethon(
            session=str(session_path),
            flag=CreateNewSession,
            api=API.TelegramDesktop.Generate(),
        )
        # Disconnect cleanly so .session file is flushed.
        res = client.disconnect()
        if asyncio.iscoroutine(res):
            await res
        return session_path, True, "ok"
    except Exception as exc:
        return session_path, False, repr(exc)


async def main(root: Path, sessions_dir: Path, *, concurrency: int = 4):
    sessions_dir.mkdir(parents=True, exist_ok=True)
    tdatas = sorted(p for p in root.rglob("tdata") if p.is_dir())
    print(f"found {len(tdatas)} tdata folders")

    sem = asyncio.Semaphore(concurrency)

    async def guarded(tdata: Path):
        async with sem:
            return await convert_one(tdata, sessions_dir)

    results = await asyncio.gather(*(guarded(t) for t in tdatas))
    for session_path, ok, reason in results:
        flag = "OK" if ok else "SKIP"
        print(f"  {flag:4s} {session_path.name:40s} {reason}")


if __name__ == "__main__":
    asyncio.run(main(
        root=Path("/path/to/backup-root"),
        sessions_dir=Path("./out-sessions"),
        concurrency=4,
    ))
```

## Tips

- **Concurrency = 2-4 is usually enough.** Each conversion talks to Telegram's auth API; pushing higher gets you rate-limited.
- **Each new session counts as a new device** in Telegram's "active sessions" list. If you only need to read messages and want to keep the device list clean, use `UseCurrentSession` instead of `CreateNewSession` (but then the original Telegram Desktop will be logged out).
- For thousands of tdata folders, persist progress to a JSON file so you can resume after failures — the example above is the minimal version.

## Read-only inspection

If you only need to know *what* accounts are in each tdata (UserId, DC, etc.) without going to the network, use the CLI. The shell loop below is sequential (use `xargs -0 -P4` if you want real parallelism):

```bash
find /backup-root -name tdata -type d -print0 | while IFS= read -r -d '' t; do
    opentele-ng info "$t" --json
done | jq -s '[.[] | .accounts[]]'
```

This never touches the Telegram API and is safe to run on any number of tdata folders.
