"""Quick benchmark: pure-Python QDataStream vs PyQt6 baseline on hot paths.

Run with PyQt6 installed (it's a test-only dependency):

    docker run --rm -v "$PWD:/work" -w /work python:3.13-slim bash -c \
        'apt-get update >/dev/null && apt-get install -y -qq libgl1 libegl1 libglib2.0-0 \
            libxkbcommon-x11-0 libdbus-1-3 libfontconfig1 >/dev/null && \
         pip install -q -e . PyQt6 && python scripts/benchmark.py'

Three operations that dominate tdata read/write cost are measured.
"""
from __future__ import annotations

import random
import statistics
import sys
import time


def _bench(label: str, fn, *, repeat: int = 1000) -> tuple[str, float]:
    samples: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        for _ in range(repeat):
            fn()
        samples.append(time.perf_counter() - t0)
    median_us = statistics.median(samples) / repeat * 1_000_000
    return label, median_us


# Seed so different invocations measure the same input bytes (timing is still
# stochastic — see _bench — but the payload itself is reproducible).
random.seed(0)
PAYLOAD_4K = bytes(random.getrandbits(8) for _ in range(4096))
TEXT_200 = "Бангкок Bangkok 🇹🇭" * 12  # ~216 chars after expansion


def run_pure() -> list[tuple[str, float]]:
    from opentele.td.qdatastream import QByteArray, QDataStream, QIODevice

    def qba_roundtrip() -> None:
        buf = QByteArray()
        s = QDataStream(buf, QIODevice.OpenModeFlag.WriteOnly)
        s << QByteArray(PAYLOAD_4K)
        out = QByteArray()
        s2 = QDataStream(buf, QIODevice.OpenModeFlag.ReadOnly)
        s2 >> out
        assert bytes(out) == PAYLOAD_4K

    def qstring_roundtrip() -> None:
        buf = QByteArray()
        s = QDataStream(buf, QIODevice.OpenModeFlag.WriteOnly)
        s.writeQString(TEXT_200)
        s2 = QDataStream(buf, QIODevice.OpenModeFlag.ReadOnly)
        out = s2.readQString()
        assert out == TEXT_200

    def uint64_chain() -> None:
        buf = QByteArray()
        s = QDataStream(buf, QIODevice.OpenModeFlag.WriteOnly)
        for i in range(50):
            s.writeUInt64(i * 0x0102030405060708)

    return [
        _bench("QByteArray 4KB roundtrip", qba_roundtrip),
        _bench("QString 200ch roundtrip", qstring_roundtrip),
        _bench("UInt64 ×50 chain", uint64_chain),
    ]


def run_pyqt() -> list[tuple[str, float]] | None:
    try:
        from PyQt6.QtCore import QByteArray, QDataStream, QIODevice  # type: ignore
    except ImportError:
        return None

    def qba_roundtrip() -> None:
        buf = QByteArray()
        s = QDataStream(buf, QIODevice.OpenModeFlag.WriteOnly)
        s << QByteArray(PAYLOAD_4K)
        out = QByteArray()
        s2 = QDataStream(buf, QIODevice.OpenModeFlag.ReadOnly)
        s2 >> out
        assert bytes(out) == PAYLOAD_4K

    def qstring_roundtrip() -> None:
        buf = QByteArray()
        s = QDataStream(buf, QIODevice.OpenModeFlag.WriteOnly)
        s.writeQString(TEXT_200)
        s2 = QDataStream(buf, QIODevice.OpenModeFlag.ReadOnly)
        out = s2.readQString()
        assert out == TEXT_200

    def uint64_chain() -> None:
        buf = QByteArray()
        s = QDataStream(buf, QIODevice.OpenModeFlag.WriteOnly)
        for i in range(50):
            s.writeUInt64(i * 0x0102030405060708)

    return [
        _bench("QByteArray 4KB roundtrip", qba_roundtrip),
        _bench("QString 200ch roundtrip", qstring_roundtrip),
        _bench("UInt64 ×50 chain", uint64_chain),
    ]


def main() -> int:
    import opentele

    pure = run_pure()
    pyqt = run_pyqt()

    print(f"Python {sys.version.split()[0]}  |  opentele.__version__ = {opentele.__version__}")
    print()
    print(f"{'Operation':<28} {'pure-Python (µs)':>18} {'PyQt6 (µs)':>14} {'ratio':>8}")
    print("-" * 72)

    pyqt_map = {label: v for label, v in pyqt} if pyqt else {}
    for label, pv in pure:
        qv = pyqt_map.get(label)
        if qv is None:
            print(f"{label:<28} {pv:>18.2f} {'(PyQt absent)':>14}  {'-':>8}")
        else:
            ratio = pv / qv
            print(f"{label:<28} {pv:>18.2f} {qv:>14.2f} {ratio:>7.2f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
