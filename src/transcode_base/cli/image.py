from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import cast

from ..profiles import image as _prof
from ..profiles.base import RawProfile, load_profile
from ..runners.image import Image
from ._utils import kv_type


def main() -> None:
    p = argparse.ArgumentParser(description="Encode a single image.")
    p.add_argument("input", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--backend", required=True, metavar="BACKEND")
    p.add_argument("--arg", metavar="KEY=VALUE", action="append", default=[], type=kv_type)
    p.add_argument("--dry-run", action="store_true")
    ns = p.parse_args()

    fmt = ns.output.suffix.lstrip(".")
    raw = {fmt: {ns.backend: {"args": dict(ns.arg)}}} if ns.arg else {}
    profile = load_profile(_prof.Profile, cast(RawProfile, raw))
    runner = Image(
        input=ns.input,
        output=ns.output,
        profile=profile,
        format=fmt,
        backend=ns.backend,
    )
    if ns.dry_run:
        print(shlex.join(runner.build_cmd()))
    else:
        runner.run()
