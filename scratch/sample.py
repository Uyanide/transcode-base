#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# ///
"""Extract short benchmark samples from a video.

Picks two kinds of samples:
  - K "scene" samples — top-K by score from a scd.py JSON, pruned to enforce
    minimum spacing. These are the high-value moments (cuts, motion peaks).
  - N "uniform" samples — evenly distributed across the video timeline,
    dropped if too close to any already-picked scene timestamp.

Each pick is extracted as a lossless FFV1 / yuv420p10le `.mkv` clip via
input-side `-ss` (keyframe-snapped — fine for benchmarking, not frame-accurate).
Emits a JSON summary describing every produced sample to stdout.
"""

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Sample:
    index: int
    time: float
    source: str  # "scene" | "uniform"
    path: Path


def probe_duration(input_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        str(input_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(proc.stdout.strip())


def load_scenes(path: Path) -> list[tuple[float, float]]:
    data = json.loads(path.read_text())
    return [(float(e["time"]), float(e["score"])) for e in data]


def pick_scene_times(
    scenes: list[tuple[float, float]],
    *,
    count: int,
    min_sep: float,
) -> list[float]:
    """Top-by-score, greedy with min-separation. May return fewer than `count`
    if candidates are sparse or too clustered."""
    if count <= 0 or not scenes:
        return []
    ranked = sorted(scenes, key=lambda x: -x[1])
    kept: list[float] = []
    for t, _ in ranked:
        if all(abs(t - k) >= min_sep for k in kept):
            kept.append(t)
            if len(kept) >= count:
                break
    return sorted(kept)


def pick_uniform_times(
    duration: float,
    *,
    count: int,
    sample_dur: float,
    avoid: list[float],
    min_sep: float,
) -> list[float]:
    """Evenly-spaced timestamps inside [0, duration - sample_dur], filtered to
    keep at least `min_sep` from any timestamp in `avoid`. May return fewer
    than `count`."""
    if count <= 0 or duration <= sample_dur:
        return []
    available = duration - sample_dur
    candidates = [available * (i + 0.5) / count for i in range(count)]
    return [t for t in candidates if all(abs(t - a) >= min_sep for a in avoid)]


def extract(input_path: Path, output_path: Path, *, time: float, duration: float) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-y",
        "-ss",
        f"{time:.3f}",
        "-i",
        str(input_path),
        "-t",
        f"{duration:.3f}",
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-c:v",
        "ffv1",
        "-level",
        "3",
        "-coder",
        "1",
        "-context",
        "1",
        "-g",
        "1",
        "-pix_fmt",
        "yuv420p10le",
        str(output_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed for {output_path} (rc={proc.returncode}):\n{proc.stderr}"
        )


def main() -> None:
    p = argparse.ArgumentParser(description="Extract benchmark samples from a video.")
    p.add_argument("input", type=Path)
    p.add_argument("output_dir", type=Path)
    p.add_argument(
        "--scenes",
        type=Path,
        help="JSON list of {time, score} from scd.py (optional; omit for uniform-only)",
    )
    p.add_argument(
        "--count-scene",
        type=int,
        default=3,
        help="how many top-score scene samples to pick (default 3)",
    )
    p.add_argument(
        "--count-uniform",
        type=int,
        default=5,
        help="how many uniformly-spaced samples to pick (default 5)",
    )
    p.add_argument(
        "--duration", type=float, default=10.0, help="sample length in seconds (default 10)"
    )
    p.add_argument(
        "--min-sep",
        type=float,
        default=30.0,
        help="minimum gap between any two sample starts (default 30)",
    )
    p.add_argument(
        "--workers", type=int, default=4, help="parallel ffmpeg extract workers (default 4)"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the chosen plan as JSON without extracting any clips",
    )
    args = p.parse_args()

    if args.min_sep < args.duration:
        sys.exit(f"--min-sep ({args.min_sep}) must be >= --duration ({args.duration})")

    duration = probe_duration(args.input)
    scenes = load_scenes(args.scenes) if args.scenes else []

    scene_times = pick_scene_times(scenes, count=args.count_scene, min_sep=args.min_sep)
    uniform_times = pick_uniform_times(
        duration,
        count=args.count_uniform,
        sample_dur=args.duration,
        avoid=scene_times,
        min_sep=args.min_sep,
    )

    plan = sorted(
        [(t, "scene") for t in scene_times] + [(t, "uniform") for t in uniform_times],
        key=lambda x: x[0],
    )
    samples = [
        Sample(i, t, src, args.output_dir / f"sample_{i:02d}.mkv")
        for i, (t, src) in enumerate(plan)
    ]
    summary = [
        {"index": s.index, "time": s.time, "source": s.source, "path": str(s.path)} for s in samples
    ]

    if args.dry_run:
        print(json.dumps(summary, indent=2))
        return

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(
            ex.map(
                lambda s: extract(args.input, s.path, time=s.time, duration=args.duration),
                samples,
            )
        )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
