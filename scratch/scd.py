#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""Scene-change detection via ffmpeg's `scdet` filter.

Emits a JSON list of `{time, score}` for every detected scene change. Score is
scdet's raw value (roughly 0-100, higher = stronger change); the threshold
trims the list, the score itself is preserved so downstream consumers (e.g.
sample picker) can prioritise by magnitude rather than just by time.
"""

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SceneChange:
    time: float
    score: float


def detect(input_path: Path, *, threshold: float, downscale: int) -> list[SceneChange]:
    parts: list[str] = []
    if downscale > 0:
        parts.append(f"scale={downscale}:-2:flags=fast_bilinear")
    parts.append(f"scdet=t={threshold}:s=1")
    parts.append("metadata=mode=print:file=-")
    vf = ",".join(parts)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-i",
        str(input_path),
        "-an",
        "-sn",
        "-map",
        "0:v:0",
        "-vf",
        vf,
        "-f",
        "null",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        sys.exit(proc.returncode)
    return _parse(proc.stdout)


def _parse(text: str) -> list[SceneChange]:
    # metadata=print emits per-frame blocks:
    #     frame:N    pts:P    pts_time:T
    #     lavfi.scd.mafd=...
    #     lavfi.scd.score=...
    # scdet with s=1 only lets scene-change frames pass, so every block here
    # is a detected change.
    blocks = re.split(r"(?=^frame:)", text, flags=re.MULTILINE)
    out: list[SceneChange] = []
    for block in blocks:
        time_m = re.search(r"pts_time:([\d.]+)", block)
        score_m = re.search(r"lavfi\.scd\.score=([\d.]+)", block)
        if time_m and score_m:
            out.append(SceneChange(float(time_m.group(1)), float(score_m.group(1))))
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Detect scene changes via ffmpeg scdet.")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path, help="JSON output path (default: stdout)")
    p.add_argument(
        "-t",
        "--threshold",
        type=float,
        default=10.0,
        help="scdet threshold (default 10; 5-15 typical, lower = more sensitive)",
    )
    p.add_argument(
        "--downscale",
        type=int,
        default=480,
        help="downscale width for detection speed (0 to disable, default 480)",
    )
    args = p.parse_args()

    scenes = detect(args.input, threshold=args.threshold, downscale=args.downscale)
    payload = json.dumps(
        [{"time": s.time, "score": s.score} for s in scenes],
        indent=2,
    )
    if args.output:
        args.output.write_text(payload + "\n")
    else:
        print(payload)


if __name__ == "__main__":
    main()
