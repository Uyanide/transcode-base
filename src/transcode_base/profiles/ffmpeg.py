"""Typed profile for the ffmpeg subsystem.

Mirrors `ffmpeg.toml`:

    filtergraph          string, passed as-is to `-filter_complex`
    [video.<encoder>]    flat key/value table, each becomes `-key value` on the CLI
    [audio.<encoder>]    same shape, used for `-c:a`
"""

from __future__ import annotations

from attrs import frozen

from .base import RawProfile, as_str


@frozen
class EncoderProfile:
    """A [video.<name>] or [audio.<name>] section. Each (k, v) maps to '-k v' on the ffmpeg CLI."""

    flags: dict[str, str]


@frozen
class Profile:
    filters: list[str]
    video: dict[str, EncoderProfile]
    audio: dict[str, EncoderProfile]

    @classmethod
    def from_raw(cls, raw: RawProfile) -> Profile:
        filters: list[str] = []
        if "filters" in raw:
            filters_raw = raw["filters"]
            if not isinstance(filters_raw, list) or not all(
                isinstance(f, str) for f in filters_raw
            ):
                msg = "ffmpeg profile: filters must be a list of strings"
                raise ValueError(msg)
            filters = filters_raw  # type: ignore[list-item]

        return cls(
            filters=filters,
            video=_parse_kind(raw, "video"),
            audio=_parse_kind(raw, "audio"),
        )

    @staticmethod
    def default_name() -> str:
        return "ffmpeg"


def _parse_kind(raw: RawProfile, kind: str) -> dict[str, EncoderProfile]:
    section = raw.get(kind, {})
    if not isinstance(section, dict):
        msg = f"ffmpeg profile: {kind!r} must be a table"
        raise ValueError(msg)
    out: dict[str, EncoderProfile] = {}
    for encoder_name, encoder_data in section.items():
        if not isinstance(encoder_data, dict):
            msg = f"ffmpeg profile: {kind}.{encoder_name!r} must be a table"
            raise ValueError(msg)
        flags = {k: as_str(v, f"{kind}.{encoder_name}.{k}") for k, v in encoder_data.items()}
        out[encoder_name] = EncoderProfile(flags=flags)
    return out
