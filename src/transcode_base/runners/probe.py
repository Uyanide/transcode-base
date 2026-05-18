"""ffprobe-based probe task."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path

from attr import define, frozen

from ..utils import promote
from .base import ShellRunResult, shell

__all__ = [
    "Option",
    "Result",
    "Runner",
]


class Option(StrEnum):
    FPS = "fps"
    FRAMES = "frames"
    DURATION = "duration"


@frozen
class Result(ShellRunResult):
    input: Path
    fps: str | None = None
    frames: int | None = None
    duration: float = 0.0


@define
class Runner:
    input: Path
    options: set[Option]

    def build_cmd(self) -> list[str]:
        stream_entries: list[str] = []
        if Option.FPS in self.options:
            stream_entries.append("r_frame_rate")
        if Option.FRAMES in self.options:
            stream_entries.append("nb_frames")
        if Option.DURATION in self.options:
            stream_entries.append("duration")
        stream_entries_str = ",".join(stream_entries)
        return [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            f"stream={stream_entries_str}",
            "-of",
            "json",
            str(self.input),
        ]

    def run(self) -> Result:
        result = shell(self.build_cmd(), capture=True)
        if result.stdout is None:
            msg = f"ffprobe did not produce any output for {self.input}"
            raise RuntimeError(msg)
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            msg = f"ffprobe output is not valid JSON for {self.input}"
            raise RuntimeError(msg) from e
        streams = data.get("streams")
        if not isinstance(streams, list) or not streams:
            msg = f"ffprobe output does not contain any streams for {self.input}"
            raise RuntimeError(msg)
        stream = streams[0]
        fps = stream.get("r_frame_rate")
        frames_str = stream.get("nb_frames")
        duration_str = stream.get("duration")
        frames = int(frames_str) if isinstance(frames_str, str) and frames_str.isdigit() else None
        try:
            duration = float(duration_str) if isinstance(duration_str, str) else None
        except ValueError:
            duration = None
        return promote(
            result,
            Result,
            input=self.input,
            fps=fps,
            frames=frames,
            duration=duration,
        )
