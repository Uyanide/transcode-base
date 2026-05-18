"""Typed profile for the av1an subsystem.

Mirrors `av1an.toml`. The contract: every key that is not one of the structural
names (`audio`, `tq`, `cq`, `video-params`, `audio-params`, `args`, `probe`) is
treated as a literal av1an CLI flag, with the TOML key being the flag name
(kebab-case) and the TOML value being the flag's argument.

* `[audio.<name>]` has `audio-params` (template) + `args.*` (render context).
* `[<mode>.<encoder>]` has `video-params` (template) + `args.*` (render context).
  An optional `probe.*` sub-subtable overlays `args` when rendering for
  probing (emitted as `--probe-video-params`).
  Other keys at this level are also treated as flags, which is useful for
  encoder-specific flags overriding.

Scalars directly under `[tq]` / `[cq]` and at the top level become av1an flags
verbatim. Empty string deletes.
"""

from __future__ import annotations

from attrs import frozen

from .base import RawProfile, as_str, get_str

# Reserved structural keys (anything else under that scope is a passthrough flag).
_TOP_RESERVED = frozenset({"audio", "tq", "cq"})
_SECTION_PARAMS = frozenset({"video-params", "audio-params", "args", "probe"})


@frozen
class AudioProfile:
    """[audio.<name>]: audio_params template + render context."""

    audio_params: str
    args: dict[str, str]


@frozen
class EncoderProfile:
    """[<mode>.<encoder>]: video_params template, args for the main render,
    probe_args (from args.probe) overlaid on args when rendering for probing."""

    video_params: str
    flags: dict[str, str]
    args: dict[str, str]
    probe_args: dict[str, str]


@frozen
class ModeProfile:
    """[tq] or [cq]: flat scalar flags (e.g. target-metric, target-quality)
    + per-encoder subtables."""

    flags: dict[str, str]
    encoders: dict[str, EncoderProfile]


@frozen
class Profile:
    """Top-level scalars become av1an flags; `audio`/`tq`/`cq` are structural."""

    flags: dict[str, str]
    audio: dict[str, AudioProfile]
    tq: ModeProfile
    cq: ModeProfile

    @classmethod
    def from_raw(cls, raw: RawProfile) -> Profile:
        flags: dict[str, str] = {}
        for k, v in raw.items():
            if k in _TOP_RESERVED:
                continue
            flags[k] = as_str(v, f"<top>.{k}")
        return cls(
            flags=flags,
            audio=_parse_audio_section(raw),
            tq=_parse_mode(raw, "tq"),
            cq=_parse_mode(raw, "cq"),
        )

    @staticmethod
    def default_name() -> str:
        return "av1an"


def _parse_audio_section(raw: RawProfile) -> dict[str, AudioProfile]:
    section = raw.get("audio", {})
    if not isinstance(section, dict):
        msg = "av1an profile: 'audio' must be a table"
        raise ValueError(msg)
    out: dict[str, AudioProfile] = {}
    for name, data in section.items():
        if not isinstance(data, dict):
            msg = f"av1an profile: audio.{name!r} must be a table"
            raise ValueError(msg)
        out[name] = _parse_audio(data, f"audio.{name}")
    return out


def _parse_audio(data: RawProfile, where: str) -> AudioProfile:
    audio_params = get_str(data, "audio-params", where)
    args = _parse_args(data, where)
    return AudioProfile(audio_params=audio_params, args=args)


def _parse_mode(raw: RawProfile, mode: str) -> ModeProfile:
    section = raw.get(mode, {})
    if not isinstance(section, dict):
        msg = f"av1an profile: {mode!r} must be a table"
        raise ValueError(msg)
    flags: dict[str, str] = {}
    encoders: dict[str, EncoderProfile] = {}
    for k, v in section.items():
        if isinstance(v, dict):
            encoders[k] = _parse_encoder(v, f"{mode}.{k}")
        elif isinstance(v, str):
            flags[k] = v
        else:
            msg = f"av1an profile: {mode}.{k} must be a string flag or a subtable"
            raise ValueError(msg)
    return ModeProfile(flags=flags, encoders=encoders)


def _parse_encoder(data: RawProfile, where: str) -> EncoderProfile:
    video_params = get_str(data, "video-params", where)
    args = _parse_args(data, where, key="args")
    probe_args = _parse_args(data, where, key="probe")
    flags = _unknown_section_keys_as_flags(data, where)
    return EncoderProfile(video_params=video_params, flags=flags, args=args, probe_args=probe_args)


def _unknown_section_keys_as_flags(data: RawProfile, where: str) -> dict[str, str]:
    """Catch typos like `vide-params` early — encoder/audio sections only accept
    the structural keys; everything else lives under `args`."""
    flags: dict[str, str] = {}
    for k in data:
        if k not in _SECTION_PARAMS:
            flags[k] = as_str(data[k], f"{where}.{k}")
    return flags


def _parse_args(data: RawProfile, where: str, key: str = "args") -> dict[str, str]:
    args_raw = data.get(key, {})
    if not isinstance(args_raw, dict):
        msg = f"av1an profile: {where}.{key} must be a table"
        raise ValueError(msg)
    out: dict[str, str] = {}
    for k, v in args_raw.items():
        out[k] = as_str(v, f"{where}.{key}.{k}")
    return out
