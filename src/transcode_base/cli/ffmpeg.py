from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from typing import cast

from ..profiles import ffmpeg as _prof
from ..profiles.base import RawProfile, load_profile
from ..runners.ffmpeg import FFmpeg
from ._utils import kv_type


def main() -> None:
    p = argparse.ArgumentParser(description="Encode a video with ffmpeg.")
    p.add_argument("input", type=Path)
    p.add_argument("-o", "--output", type=Path)
    p.add_argument("--video", default="libsvtav1", metavar="ENCODER")
    p.add_argument("--audio", default="copy", metavar="ENCODER")
    p.add_argument("--no-video", action="store_true")
    p.add_argument("--no-audio", action="store_true")
    p.add_argument("--arg", metavar="KEY=VALUE", action="append", default=[], type=kv_type)
    p.add_argument(
        "--audio-arg",
        metavar="KEY=VALUE",
        action="append",
        default=[],
        type=kv_type,
        dest="audio_arg",
    )
    p.add_argument("--dry-run", action="store_true")
    ns = p.parse_args()

    video: str | None = None if ns.no_video else ns.video
    audio: str | None = None if ns.no_audio else ns.audio
    output = ns.output or ns.input.with_name(
        f"{ns.input.stem}.{video or 'novideo'}.{audio or 'noaudio'}.mkv"
    )

    raw: dict[str, dict[str, dict[str, str]]] = {}
    if ns.arg and video:
        raw["video"] = {video: dict(ns.arg)}
    if ns.audio_arg and audio:
        raw["audio"] = {audio: dict(ns.audio_arg)}

    profile = load_profile(_prof.Profile, cast(RawProfile, raw))
    runner = FFmpeg(
        input=ns.input,
        output=output,
        profile=profile,
        video=video,
        audio=audio,
    )
    if ns.dry_run:
        print(shlex.join(runner.build_cmd()))
    else:
        runner.run()
