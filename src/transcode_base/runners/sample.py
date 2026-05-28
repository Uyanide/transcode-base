"""Scene-change detection and sample-extraction runners."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from pathlib import Path

from attrs import define, field, frozen

from ..profiles.sample import SampleProfile, SCDProfile
from . import probe
from .base import shell

__all__ = [
    "SCD",
    "SCDProfile",
    "SCDResult",
    "Sample",
    "SampleProfile",
    "SampleResult",
    "SampleSlice",
    "SampleSourceType",
    "SceneChange",
]


@frozen
class SceneChange:
    time: float
    score: float


@frozen
class SCDResult:
    input: Path
    scene_changes: list[SceneChange]


@define
class SCD:
    input: Path
    profile: SCDProfile

    def build_cmd(self) -> list[str]:
        parts: list[str] = []
        if self.profile.downscale > 0:
            parts.append(f"scale={self.profile.downscale}:-2:flags=fast_bilinear")
        parts.append(f"scdet=t={self.profile.threshold}:s=1")
        parts.append("metadata=mode=print:file=-")
        vf = ",".join(parts)
        return [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(self.input),
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

    def run(self) -> SCDResult:
        result = shell(self.build_cmd(), stdout=True)
        stdout_text = (result.stdout or b"").decode()
        return SCDResult(input=self.input, scene_changes=_parse_scenes(stdout_text))


def _parse_scenes(text: str) -> list[SceneChange]:
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


class SampleSourceType(StrEnum):
    SCENE = "scene"
    UNIFORM = "uniform"


@frozen
class SampleSlice:
    index: int
    time: float
    source: SampleSourceType
    path: Path


@frozen
class SampleResult:
    input: Path
    output_dir: Path
    samples: list[SampleSlice]


@define
class Sample:
    input: Path
    output_dir: Path
    profile: SampleProfile
    pix_fmt: str | None = None
    scenes: list[SceneChange] = field(factory=list)

    def run(self) -> SampleResult:
        duration = probe.Probe(input=self.input, options={probe.Option.DURATION}).run().duration

        scene_pairs = [(s.time, s.score) for s in self.scenes]
        scene_times = _pick_scene_times(
            scene_pairs,
            count=self.profile.count_scene,
            min_sep=self.profile.min_separation,
            duration=duration,
            sample_dur=self.profile.duration,
        )
        uniform_times = _pick_uniform_times(
            duration,
            count=self.profile.count_uniform,
            sample_dur=self.profile.duration,
            avoid=scene_times,
            min_sep=self.profile.min_separation,
        )

        plan = sorted(
            [(t, SampleSourceType.SCENE) for t in scene_times]
            + [(t, SampleSourceType.UNIFORM) for t in uniform_times],
            key=lambda x: x[0],
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        samples = [
            SampleSlice(i, t, src, self.output_dir / f"sample_{i:02d}.mkv")
            for i, (t, src) in enumerate(plan)
        ]
        with ThreadPoolExecutor(max_workers=self.profile.workers) as ex:
            list(ex.map(lambda s: self._extract(s.path, s.time), samples))
        return SampleResult(input=self.input, output_dir=self.output_dir, samples=samples)

    def _extract(self, output_path: Path, time: float) -> None:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-y",
            "-ss",
            f"{time:.3f}",
            "-i",
            str(self.input),
            "-t",
            f"{self.profile.duration:.3f}",
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
        ]
        if self.pix_fmt:
            cmd.extend(["-pix_fmt", self.pix_fmt])
        if self.profile.workers > 1:
            cmd.extend(["-threads", "2"])
        cmd.append(str(output_path))
        result = shell(cmd, check=False, stderr=True)
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode()
            msg = f"ffmpeg failed for {output_path} (rc={result.returncode}):\n{stderr}"
            raise RuntimeError(msg)


def _pick_scene_times(
    scenes: list[tuple[float, float]],
    *,
    count: int,
    min_sep: float,
    duration: float | None,
    sample_dur: float,
) -> list[float]:
    """Top-by-score, greedy with min-separation. May return fewer than `count`
    if candidates are sparse or too clustered."""
    if count <= 0 or not scenes:
        return []
    if duration is not None:
        scenes = [(t, s) for t, s in scenes if 0 <= t <= duration - sample_dur]
    else:
        scenes = [(t, s) for t, s in scenes if t >= 0]
    ranked = sorted(scenes, key=lambda x: -x[1])
    kept: list[float] = []
    for t, _ in ranked:
        if all(abs(t - k) >= min_sep for k in kept):
            kept.append(t)
            if len(kept) >= count:
                break
    return sorted(kept)


def _pick_uniform_times(
    duration: float | None,
    *,
    count: int,
    sample_dur: float,
    avoid: list[float],
    min_sep: float,
) -> list[float]:
    """Evenly-spaced timestamps inside [0, duration - sample_dur], filtered to
    keep at least `min_sep` from any timestamp in `avoid`. May return fewer
    than `count`."""
    if count <= 0 or duration is None or duration <= sample_dur:
        return []
    available = duration - sample_dur
    candidates = [available * (i + 0.5) / count for i in range(count)]
    return [t for t in candidates if all(abs(t - a) >= min_sep for a in avoid)]
