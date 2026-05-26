from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..runners.metric import (
    PSNR,
    SSIM,
    SSIMULACRA2,
    VMAF,
    XPSNR,
    Butteraugli,
    ChannelStats,
)

_CHOICES = ["ssim", "psnr", "xpsnr", "vmaf", "ssimulacra2", "butteraugli"]

_SUFFIXES: dict[str, str] = {
    "ssim": ".txt",
    "psnr": ".txt",
    "xpsnr": ".txt",
    "vmaf": ".json",
    "ssimulacra2": ".json",
    "butteraugli": ".json",
}


def _print_channels(channels: dict[str, ChannelStats]) -> None:
    for name, ch in channels.items():
        print(
            f"{name}:"
            f"  mean={ch.mean:.4f}"
            f"  hmean={ch.harmonic_mean:.4f}"
            f"  std={ch.std:.4f}"
            f"  median={ch.median:.4f}"
            f"  p5={ch.p5:.4f}  p95={ch.p95:.4f}"
            f"  min={ch.min:.4f}  max={ch.max:.4f}"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="Measure video quality (reference vs. distorted).")
    p.add_argument("reference", type=Path)
    p.add_argument("distorted", type=Path)
    p.add_argument("type", choices=_CHOICES)
    p.add_argument("--threads", type=int)
    p.add_argument("--every", type=int)
    p.add_argument("--dry-run", action="store_true")
    ns = p.parse_args()

    kind: str = ns.type
    threads: int | None = ns.threads
    every: int | None = ns.every

    with NamedTemporaryFile(suffix=_SUFFIXES[kind]) as tmp:
        log = Path(tmp.name)

        if kind == "ssim":
            runner = SSIM(
                reference=ns.reference,
                distorted=ns.distorted,
                every=every if every is not None else 1,
                log_path=log,
            )
        elif kind == "psnr":
            runner = PSNR(
                reference=ns.reference,
                distorted=ns.distorted,
                every=every if every is not None else 1,
                log_path=log,
            )
        elif kind == "xpsnr":
            runner = XPSNR(
                reference=ns.reference,
                distorted=ns.distorted,
                every=every if every is not None else 1,
                log_path=log,
            )
        elif kind == "vmaf":
            runner = VMAF(
                reference=ns.reference,
                distorted=ns.distorted,
                threads=threads if threads is not None else 4,
                subsample=every if every is not None else 1,
                log_path=log,
            )
        elif kind == "ssimulacra2":
            runner = SSIMULACRA2(
                reference=ns.reference,
                distorted=ns.distorted,
                threads=threads if threads is not None else 2,
                every=every if every is not None else 1,
                log_path=log,
            )
        elif kind == "butteraugli":
            runner = Butteraugli(
                reference=ns.reference,
                distorted=ns.distorted,
                threads=threads if threads is not None else 2,
                every=every if every is not None else 1,
                log_path=log,
            )
        else:
            raise AssertionError(kind)

        if ns.dry_run:
            print(shlex.join(runner.build_cmd()))
            return

        _print_channels(runner.run().channels)
