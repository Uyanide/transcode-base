from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import cast

from ..profiles import av1an as _prof
from ..profiles.base import RawProfile, load_profile
from ..runners.av1an import Av1an, Mode
from ._utils import kv_type


def main() -> None:
    p = argparse.ArgumentParser(description="Encode a video with av1an.")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path)
    p.add_argument("--video", default="svt-av1", metavar="ENCODER")
    p.add_argument("--audio", default="copy", metavar="ENCODER")
    p.add_argument("--mode", default="tq", choices=["tq", "cq"])
    p.add_argument("--arg", metavar="KEY=VALUE", action="append", default=[], type=kv_type)
    p.add_argument("--probe", metavar="KEY=VALUE", action="append", default=[], type=kv_type)
    p.add_argument("--dry-run", action="store_true")
    ns = p.parse_args()

    output = ns.output or ns.input.with_name(f"{ns.input.stem}.av1an.{ns.video}.{ns.audio}.mkv")

    enc: dict[str, dict[str, str]] = {}
    if ns.arg:
        enc["args"] = dict(ns.arg)
    if ns.probe:
        enc["probe"] = dict(ns.probe)

    override = cast(RawProfile, {ns.mode: {ns.video: enc}} if enc else {})
    profile = load_profile(_prof.Profile, override)
    runner = Av1an(
        input=ns.input,
        output=output,
        profile=profile,
        mode=Mode(ns.mode),
        encoder=ns.video,
        audio=ns.audio,
    )
    if ns.dry_run:
        print(shlex.join(runner.build_cmd()))
    else:
        runner.run()
