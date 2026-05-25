from __future__ import annotations

import argparse
import shlex
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast

from ..profiles import image as _prof
from ..profiles.base import RawProfile, load_profile
from ..runners.image import Image
from ._utils import kv_type


def _needs_update(src: Path, dst: Path) -> bool:
    return not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime


def main() -> None:
    p = argparse.ArgumentParser(description="Batch-encode images (incremental).")
    p.add_argument("input_dir", type=Path)
    p.add_argument("output_dir", type=Path)
    p.add_argument("--format", required=True, metavar="FORMAT")
    p.add_argument("--backend", required=True, metavar="BACKEND")
    p.add_argument(
        "--ext",
        metavar="EXT",
        help="output extension, e.g. .avif (default: .<format>)",
    )
    p.add_argument("--glob", default="*", metavar="PATTERN")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--arg", metavar="KEY=VALUE", action="append", default=[], type=kv_type)
    p.add_argument("--dry-run", action="store_true")
    ns = p.parse_args()

    ext = ns.ext or f".{ns.format}"
    if not ext.startswith("."):
        ext = f".{ext}"

    inputs = sorted(ns.input_dir.glob(ns.glob))
    if not inputs:
        sys.exit(f"no files matched {ns.input_dir}/{ns.glob}")

    ns.output_dir.mkdir(parents=True, exist_ok=True)

    raw = {ns.format: {ns.backend: {"args": dict(ns.arg)}}} if ns.arg else {}
    profile = load_profile(_prof.Profile, cast(RawProfile, raw))

    work: list[tuple[Path, Path]] = []
    for src in inputs:
        dst = ns.output_dir / (src.stem + ext)
        if _needs_update(src, dst):
            work.append((src, dst))

    if not work:
        print("all outputs up to date")
        return

    print(f"processing {len(work)}/{len(inputs)} files")

    errors: list[tuple[Path, BaseException]] = []

    def _run(pair: tuple[Path, Path]) -> None:
        src, dst = pair
        try:
            runner = Image(
                input=src,
                output=dst,
                profile=profile,
                format=ns.format,
                backend=ns.backend,
            )
            if ns.dry_run:
                print(shlex.join(runner.build_cmd()))
            else:
                runner.run()
        except Exception as e:
            errors.append((src, e))

    with ThreadPoolExecutor(max_workers=ns.workers) as ex:
        list(ex.map(_run, work))

    for src, err in errors:
        print(f"error: {src}: {err}", file=sys.stderr)
    if errors:
        sys.exit(1)
