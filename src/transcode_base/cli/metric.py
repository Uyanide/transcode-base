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
    Butteraugli,
    FFVshipChannel,
)

_CHOICES = ["ssim", "psnr", "vmaf", "ssimulacra2", "butteraugli"]


def _print_ffvship(channels: list[FFVshipChannel]) -> None:
    for ch in channels:
        print(
            f"{ch.name}:"
            f"  mean={ch.mean:.4f}"
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

    if kind == "ssim":
        result = SSIM(reference=ns.reference, distorted=ns.distorted).run()
        print(f"SSIM  {result.mean:.6f}")
    elif kind == "psnr":
        result = PSNR(reference=ns.reference, distorted=ns.distorted).run()
        print(
            f"PSNR"
            f"  y={result.y:.2f}"
            f"  u={result.u:.2f}"
            f"  v={result.v:.2f}"
            f"  average={result.average:.2f}"
            f"  min={result.min:.2f}"
            f"  max={result.max:.2f}"
        )
    else:
        with NamedTemporaryFile(suffix=".json") as tmp:
            if kind == "vmaf":
                runner = VMAF(
                    reference=ns.reference,
                    distorted=ns.distorted,
                    threads=threads if threads is not None else 4,
                    subsample=every if every is not None else 1,
                    log_path=Path(tmp.name),
                )
                if ns.dry_run:
                    print(shlex.join(runner.build_cmd()))
                    return
                result = runner.run()
                print(
                    f"VMAF"
                    f"  mean={result.mean:.4f}"
                    f"  harmonic_mean={result.harmonic_mean:.4f}"
                    f"  min={result.min:.4f}"
                    f"  max={result.max:.4f}"
                )
            elif kind == "ssimulacra2":
                runner = SSIMULACRA2(
                    reference=ns.reference,
                    distorted=ns.distorted,
                    threads=threads if threads is not None else 2,
                    every=every if every is not None else 1,
                    log_path=Path(tmp.name),
                )
                if ns.dry_run:
                    print(shlex.join(runner.build_cmd()))
                    return
                result = runner.run()
                _print_ffvship(result.channels)
            elif kind == "butteraugli":
                runner = Butteraugli(
                    reference=ns.reference,
                    distorted=ns.distorted,
                    threads=threads if threads is not None else 2,
                    every=every if every is not None else 1,
                    log_path=Path(tmp.name),
                )
                if ns.dry_run:
                    print(shlex.join(runner.build_cmd()))
                    return
                result = runner.run()
                _print_ffvship(result.channels)
