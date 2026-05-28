"""av1an-based encode task."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from attrs import define, frozen

from ..profiles.av1an import (
    EncoderProfile,
    ModeProfile,
    Profile,
)
from ..utils import render
from .base import ShellRunResult, shell

__all__ = [
    "Av1an",
    "Mode",
    "Profile",
    "Result",
]


class Mode(StrEnum):
    TQ = "tq"
    CQ = "cq"


@frozen
class Result:
    input: Path
    output: Path
    shell: ShellRunResult


@define
class Av1an:
    input: Path
    output: Path
    profile: Profile
    mode: Mode
    encoder: str
    audio: str | None = None

    def build_cmd(self) -> list[str]:
        encoder_cfg = _select_encoder(self.profile, self.mode, self.encoder)
        mode_profile = self.profile.tq if self.mode is Mode.TQ else self.profile.cq

        flags = {}
        _update_flags(flags, self.profile.flags)
        _update_flags(flags, mode_profile.flags)
        _update_flags(flags, encoder_cfg.flags)
        flags["encoder"] = self.encoder

        video_params = render(encoder_cfg.video_params, encoder_cfg.args)
        flags["video-params"] = video_params

        probe_ctx = {**encoder_cfg.args, **encoder_cfg.probe_args}
        probe_video_params = render(encoder_cfg.video_params, probe_ctx)
        flags["probe-video-params"] = probe_video_params

        if self.audio is not None:
            try:
                audio_cfg = self.profile.audio[self.audio]
            except KeyError:
                available = ", ".join(sorted(self.profile.audio)) or "<none>"
                msg = f"unknown av1an audio profile {self.audio!r}; available: {available}"
                raise KeyError(msg) from None
            audio_params = render(audio_cfg.audio_params, audio_cfg.args)
            flags["audio-params"] = audio_params

        cmd = ["av1an"]
        for k, v in flags.items():
            cmd.append(f"--{k}")
            cmd.append(v)
        cmd.append("-i")
        cmd.append(str(self.input))
        cmd.append("-o")
        cmd.append(str(self.output))
        return cmd

    def run(self) -> Result:
        result = shell(self.build_cmd())
        return Result(input=self.input, output=self.output, shell=result)


def _select_encoder(profile: Profile, mode: Mode, name: str) -> EncoderProfile:
    section: ModeProfile = profile.tq if mode is Mode.TQ else profile.cq
    try:
        return section.encoders[name]
    except KeyError:
        available = ", ".join(sorted(section.encoders)) or "<none>"
        msg = f"unknown av1an encoder {mode.value}.{name!r}; available: {available}"
        raise KeyError(msg) from None


def _update_flags(base: dict[str, str], update: dict[str, str]):
    for k, v in update.items():
        if k in base:
            if not v:
                del base[k]
            else:
                base[k] = v
        else:
            if v:
                base[k] = v
