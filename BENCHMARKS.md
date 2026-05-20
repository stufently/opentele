# Benchmarks

`opentele-ng` ships a pure-Python `QDataStream` replacement (`opentele.td.qdatastream`) in place of PyQt's C++ implementation. This file documents what that costs you in CPU.

## Methodology

`scripts/benchmark.py` measures three micro-operations that dominate tdata serialization cost:

- **QByteArray 4KB roundtrip** — write + read of a 4 KB random binary blob through a fresh `QDataStream` pair.
- **QString 200ch roundtrip** — write + read of a 200-char string mixing Cyrillic / Latin / emoji.
- **UInt64 ×50 chain** — write 50 consecutive `uint64` values into a single stream.

Each operation runs 5 trials of 1000 iterations; the table reports the median µs / iteration.

## Results

Run on a workstation host (`Linux 6.8.0-60-generic`), inside `python:3.13-slim`, Python 3.13.13, PyQt6 6.10.x, opentele-ng 1.1.0:

| Operation                | pure-Python (µs) | PyQt6 (µs) | ratio  |
| ------------------------ | ---------------: | ---------: | -----: |
| QByteArray 4KB roundtrip |             6.50 |       3.27 |  1.99× |
| QString 200ch roundtrip  |             5.71 |       3.81 |  1.50× |
| UInt64 ×50 chain         |            36.73 |       9.40 |  3.91× |

## What this means in practice

A typical Telegram Desktop tdata folder is loaded in a single call to `TDesktop(path)`. That single call:

- Reads 4–6 files from disk (latency-bound, milliseconds).
- AES-IGE256-decrypts ~1–5 KB of map data (CPU-bound but tiny — microseconds).
- Walks ~10–50 lskType entries; each entry is one or two `uint64` plus optional `QByteArray`.

In rough terms the load path is bottlenecked by disk + AES, not by stream serialization. The pure-Python `QDataStream` adds ~tens of microseconds total per `TDesktop.LoadTData()`. That is invisible against the ~5–10 ms baseline cost.

If you are doing **batch conversion of thousands of tdata folders**, the per-folder difference is still ~10–50 µs of pure-Python overhead — negligible compared to disk I/O. If you do see a real-world hot path where this matters, please file an issue with the reproducer; we can optimize specific methods.

## How to reproduce

```bash
docker run --rm -v "$PWD:/work" -w /work python:3.13-slim bash -c '
    apt-get update >/dev/null && apt-get install -y -qq \
        libgl1 libegl1 libglib2.0-0 libxkbcommon-x11-0 \
        libdbus-1-3 libfontconfig1 >/dev/null
    pip install -q -e . PyQt6
    python scripts/benchmark.py
'
```
