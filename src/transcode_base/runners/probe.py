"""ffprobe-based probe task."""

from __future__ import annotations

import fractions
import json
from enum import StrEnum
from pathlib import Path

from attrs import define, frozen

from .base import ShellRunResult, shell

__all__ = [
    "Option",
    "Probe",
    "Result",
]


class Option(StrEnum):
    FPS = "fps"
    FRAMES = "frames"
    DURATION = "duration"
    PIX_FMT = "pix_fmt"
    BITRATE = "bitrate"


@frozen
class Result:
    input: Path
    pass1: ShellRunResult
    pass2: ShellRunResult | None = None
    fps: str | None = None  # e.g. "30000/1001"
    frames: int | None = None
    duration: float | None = None  # duration of the video or container in seconds
    pix_fmt: str | None = None
    bitrate: int | None = None  # bitrate of container (all streams), in bits/s


@define
class Probe:
    input: Path
    options: set[Option]

    def build_cmd_pass1(self, options) -> list[str]:
        stream_entries: list[str] = []
        format_entries: list[str] = []
        if Option.FPS in options:
            stream_entries.append("avg_frame_rate")
        if Option.FRAMES in options:
            stream_entries.append("nb_frames")
        if Option.DURATION in options:
            format_entries.append("duration")
        if Option.PIX_FMT in options:
            stream_entries.append("pix_fmt")
        if Option.BITRATE in options:
            format_entries.append("bit_rate")
        return _build_ffprobe_cmd(
            self.input,
            stream_entries,
            format_entries,
        )

    def build_cmd_pass2(self, options) -> list[str]:
        stream_entries: list[str] = []
        format_entries: list[str] = []
        if Option.DURATION in options:
            stream_entries.append("duration")
        return _build_ffprobe_cmd(
            self.input,
            stream_entries,
            format_entries,
        )

    def run(self) -> Result:
        # First pass

        pass1_options = set(self.options)
        if Option.FRAMES in self.options:
            pass1_options.add(Option.FPS)
            pass1_options.add(Option.DURATION)

        data = _run_ffprobe(self.build_cmd_pass1(pass1_options), self.input)
        pass1, stream_dict, format_dict = data
        pass2 = None

        fps = _parse_fps(self.options, stream_dict)
        frames = _parse_frames(self.options, stream_dict)
        duration = _parse_duration(self.options, format_dict)
        pix_fmt = _parse_pix_fmt(self.options, stream_dict)
        bitrate = _parse_bitrate(self.options, format_dict)

        if (
            Option.FRAMES in self.options
            and frames is None
            and duration is not None
            and fps is not None
        ):
            frames = int(float(duration) * fractions.Fraction(fps))

        # Second pass if needed

        pass2_options = set()
        if (
            # If duration is directly required
            Option.DURATION in self.options
            # Or is indirectly required for calculating frames when fps is already available
            or (Option.FRAMES in self.options and frames is None and fps is not None)
            # but not obtained in the first pass
        ) and duration is None:
            pass2_options.add(Option.DURATION)

        if pass2_options:
            data = _run_ffprobe(self.build_cmd_pass2(pass2_options), self.input)
            pass2, stream_dict, format_dict = data

            if Option.DURATION in pass2_options and duration is None:
                duration = _parse_duration(pass2_options, format_dict)

            if (
                Option.FRAMES in pass2_options
                and frames is None
                and duration is not None
                and fps is not None
            ):
                frames = int(float(duration) * fractions.Fraction(fps))

        return Result(
            input=self.input,
            pass1=pass1,
            pass2=pass2,
            fps=fps,
            frames=frames,
            duration=duration,
            bitrate=bitrate,
            pix_fmt=pix_fmt,
        )


def _build_ffprobe_cmd(
    input: Path, stream_entries: list[str], format_entries: list[str]
) -> list[str]:
    entries = []
    if stream_entries:
        entries.append(f"stream={','.join(stream_entries)}")
    if format_entries:
        entries.append(f"format={','.join(format_entries)}")

    cmds = [
        "ffprobe",
        "-v",
        "error",
    ]
    if stream_entries:
        cmds.extend(["-select_streams", "v:0"])
    if entries:
        cmds.extend(["-show_entries", ":".join(entries)])

    cmds.extend(["-of", "json", str(input)])
    return cmds


def _run_ffprobe(cmd: list[str], input_path: Path):
    result = shell(cmd, stdout=True)
    if result.stdout is None:
        msg = f"ffprobe did not produce any output for {input_path}"
        raise RuntimeError(msg)
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        msg = f"ffprobe output is not valid JSON for {input_path}"
        raise RuntimeError(msg) from e
    streams = data.get("streams", [])
    if not isinstance(streams, list):
        msg = f"ffprobe output does not contain any streams for {input_path}"
        raise RuntimeError(msg)
    stream_dict = {} if len(streams) == 0 else streams[0]
    format_dict = data.get("format", {})
    return result, stream_dict, format_dict


def _parse_fps(options: set[Option], data) -> str | None:
    return data.get("avg_frame_rate") if Option.FPS in options or Option.FRAMES in options else None


def _parse_frames(options: set[Option], data) -> int | None:
    if Option.FRAMES not in options:
        return None
    frames_str = data.get("nb_frames")
    return int(frames_str) if isinstance(frames_str, str) and frames_str.isdigit() else None


def _parse_duration(options: set[Option], data) -> float | None:
    if Option.DURATION not in options and Option.FRAMES not in options:
        return None
    duration_str = data.get("duration")
    try:
        return float(duration_str) if isinstance(duration_str, str) else None
    except ValueError:
        return None


def _parse_bitrate(options: set[Option], data) -> int | None:
    if Option.BITRATE not in options:
        return None
    bitrate_str = data.get("bit_rate")
    return int(bitrate_str) if isinstance(bitrate_str, str) and bitrate_str.isdigit() else None


def _parse_pix_fmt(options: set[Option], data) -> str | None:
    return data.get("pix_fmt") if Option.PIX_FMT in options else None
