"""ffmpeg-based 2-pass encode task."""

from pathlib import Path

from attrs import define, frozen

from ..profiles.doublepass import EncoderProfile, Profile
from .base import ShellRunResult, shell

__all__ = [
    "FFmpeg",
    "Profile",
    "Result",
]


@frozen
class Result:
    input: Path
    output: Path
    pass1: ShellRunResult
    pass2: ShellRunResult


@define
class FFmpeg:
    input: Path
    output: Path
    profile: Profile
    video: str
    audio: str | None = None
    passlogfile: Path | None = None

    def build_cmd_pass1(self) -> list[str]:
        cmd: list[str] = ["ffmpeg", "-y", "-i", str(self.input)]
        if self.profile.filters:
            cmd += ["-vf", ",".join(self.profile.filters)]
        cmd.extend(["-c:v", self.video])
        cmd += _flag_args(_lookup(self.profile.video, self.video, "video"))
        cmd += ["-pass", "1"]
        if self.passlogfile is not None:
            cmd += ["-passlogfile", str(self.passlogfile)]
        cmd += ["-an", "-f", "null", "/dev/null"]
        return cmd

    def build_cmd_pass2(self) -> list[str]:
        cmd: list[str] = ["ffmpeg", "-y", "-i", str(self.input)]
        if self.profile.filters:
            cmd += ["-vf", ",".join(self.profile.filters)]
        cmd.extend(["-c:v", self.video])
        cmd += _flag_args(_lookup(self.profile.video, self.video, "video"))
        if self.audio is not None:
            cmd.extend(["-c:a", self.audio])
            cmd += _flag_args(_lookup(self.profile.audio, self.audio, "audio"))
        else:
            cmd += ["-an"]
        cmd += ["-pass", "2"]
        if self.passlogfile is not None:
            cmd += ["-passlogfile", str(self.passlogfile)]
        cmd.append(str(self.output))
        return cmd

    def run(self) -> Result:
        cmd_pass1 = self.build_cmd_pass1()
        cmd_pass2 = self.build_cmd_pass2()

        pass1 = shell(cmd_pass1)
        pass2 = shell(cmd_pass2)

        return Result(
            pass1=pass1,
            pass2=pass2,
            input=self.input,
            output=self.output,
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
