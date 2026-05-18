"""Typed profiles for the scene-change detection and sample-extraction subsystems.

Mirrors `sample.toml`:

    [scd]
        threshold   int  # 0-100
        downscale   int  # width in pixels

    [sample]
        count_scene, count_uniform, workers   int
        duration, min_separation              int  # seconds
"""

from __future__ import annotations

from attrs import frozen

from .base import RawProfile, get_int


@frozen
class SCDProfile:
    threshold: int  # 0 to 100
    downscale: int  # width in pixels

    @classmethod
    def from_raw(cls, raw: RawProfile) -> SCDProfile:
        section = raw.get("scd", {})
        if not isinstance(section, dict):
            msg = "sample profile: 'scd' must be a table"
            raise ValueError(msg)
        return cls(
            threshold=get_int(section, "threshold", "scd"),
            downscale=get_int(section, "downscale", "scd"),
        )

    @staticmethod
    def default_name() -> str:
        return "sample"


@frozen
class SampleProfile:
    count_scene: int
    count_uniform: int
    duration: int  # sec
    min_separation: int  # sec
    workers: int

    @classmethod
    def from_raw(cls, raw: RawProfile) -> SampleProfile:
        section = raw.get("sample", {})
        if not isinstance(section, dict):
            msg = "sample profile: 'sample' must be a table"
            raise ValueError(msg)
        return cls(
            count_scene=get_int(section, "count_scene", "sample"),
            count_uniform=get_int(section, "count_uniform", "sample"),
            duration=get_int(section, "duration", "sample"),
            min_separation=get_int(section, "min_separation", "sample"),
            workers=get_int(section, "workers", "sample"),
        )

    @staticmethod
    def default_name() -> str:
        return "sample"
