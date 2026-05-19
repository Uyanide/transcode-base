from __future__ import annotations

import argparse
from pathlib import Path
from typing import cast

from ..profiles.base import RawProfile, load_profile
from ..profiles.sample import SampleProfile, SCDProfile
from ..runners.sample import SCD, Sample


def main() -> None:
    p = argparse.ArgumentParser(description="Detect scene changes and extract benchmark samples.")
    p.add_argument("input", type=Path)
    p.add_argument("output_dir", type=Path)
    p.add_argument("--threshold", type=int, metavar="0-100")
    p.add_argument("--downscale", type=int, metavar="WIDTH")
    p.add_argument("--count-scene", type=int, metavar="N")
    p.add_argument("--count-uniform", type=int, metavar="N")
    p.add_argument("--duration", type=int, metavar="SECS")
    p.add_argument("--min-separation", type=int, metavar="SECS")
    p.add_argument("--workers", type=int, metavar="N")
    ns = p.parse_args()

    scd_raw: dict[str, int] = {}
    if ns.threshold is not None:
        scd_raw["threshold"] = ns.threshold
    if ns.downscale is not None:
        scd_raw["downscale"] = ns.downscale

    sample_raw: dict[str, int] = {}
    if ns.count_scene is not None:
        sample_raw["count_scene"] = ns.count_scene
    if ns.count_uniform is not None:
        sample_raw["count_uniform"] = ns.count_uniform
    if ns.duration is not None:
        sample_raw["duration"] = ns.duration
    if ns.min_separation is not None:
        sample_raw["min_separation"] = ns.min_separation
    if ns.workers is not None:
        sample_raw["workers"] = ns.workers

    raw: dict[str, dict[str, int]] = {}
    if scd_raw:
        raw["scd"] = scd_raw
    if sample_raw:
        raw["sample"] = sample_raw
    override = cast(RawProfile, raw)

    scd_profile = load_profile(SCDProfile, override)
    sample_profile = load_profile(SampleProfile, override)

    scd_result = SCD(input=ns.input, profile=scd_profile).run()
    Sample(
        input=ns.input,
        output_dir=ns.output_dir,
        profile=sample_profile,
        scenes=scd_result.scene_changes,
    ).run()
