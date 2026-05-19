"""ffmpeg-based encode task."""

from __future__ import annotations

from pathlib import Path

from attr import define, frozen

from ..profiles.ffmpeg import EncoderProfile, Profile
from ..utils import promote
from .base import ShellRunResult, shell

__all__ = [
    "FFmpeg",
    "Profile",
    "Result",
]


@frozen
class Result(ShellRunResult):
    input: Path
    output: Path
    filters: list[str]


@define
class FFmpeg:
    input: Path
    output: Path
    profile: Profile
    video: str | None = None
    audio: str | None = None

    def build_cmd(self) -> list[str]:
        cmd: list[str] = ["ffmpeg", "-hide_banner", "-y", "-i", str(self.input)]

        if self.video is not None:
            if self.profile.filters:
                cmd += ["-vf", ",".join(self.profile.filters)]

            cmd += ["-c:v", self.video]
            cmd += _flag_args(_lookup(self.profile.video, self.video, "video"))
        else:
            cmd += ["-vn"]

        if self.audio is not None:
            cmd += ["-c:a", self.audio]
            cmd += _flag_args(_lookup(self.profile.audio, self.audio, "audio"))
        else:
            cmd += ["-an"]

        cmd.append(str(self.output))
        return cmd

    def run(self) -> Result:
        result = shell(self.build_cmd())
        return promote(
            result,
            Result,
            input=self.input,
            output=self.output,
            filters=self.profile.filters,
        )


def _lookup(table: dict[str, EncoderProfile], name: str, kind: str) -> EncoderProfile:
    try:
        return table[name]
    except KeyError:
        available = ", ".join(sorted(table)) or "<none>"
        msg = f"unknown ffmpeg {kind} encoder profile {name!r}; available: {available}"
        raise KeyError(msg) from None


def _flag_args(encoder: EncoderProfile) -> list[str]:
    out: list[str] = []
    for k, v in encoder.flags.items():
        out += [f"-{k}", v]
    return out
