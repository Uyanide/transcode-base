from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path
from typing import Protocol, cast

type TomlValue = str | int | float | bool | list["TomlValue"] | dict[str, "TomlValue"]
type RawProfile = dict[str, TomlValue]


class FromRaw[P](Protocol):
    @classmethod
    def from_raw(cls, raw: RawProfile) -> P: ...

    @staticmethod
    def default_name() -> str: ...


def load_profile[P: FromRaw](
    parser: type[P],
    *overrides: Path | RawProfile | str,
) -> P:
    """Load the bundled default for `name`, deep-merge each override in order
    (Path -> parsed TOML; dict -> used as-is), then parse to a typed profile."""
    merged = _read_default(parser.default_name())
    for ov in overrides:
        layer = (
            _read_toml(ov)
            if isinstance(ov, Path)
            else (tomllib.loads(ov) if isinstance(ov, str) else ov)
        )
        merged = deep_merge(merged, layer)
    return parser.from_raw(merged)


def _read_default(name: str) -> RawProfile:
    text = files("transcode_base.defaults").joinpath(f"{name}.toml").read_text()
    return cast(RawProfile, tomllib.loads(text))


def _read_toml(path: Path) -> RawProfile:
    return cast(RawProfile, tomllib.loads(path.read_text()))


def deep_merge(base: RawProfile, override: RawProfile) -> RawProfile:
    """Recursively merge `override` onto `base`. Empty-string values delete."""
    out: RawProfile = dict(base)
    for k, v in override.items():
        existing = out.get(k)
        if isinstance(v, dict) and isinstance(existing, dict):
            out[k] = deep_merge(existing, cast(RawProfile, v))
        elif v == "":
            out.pop(k, None)
        else:
            out[k] = v
    return out


def get_str(data: dict[str, TomlValue], key: str, where: str) -> str:
    return as_str(data.get(key), f"{where}.{key}")


def as_str(v: TomlValue | None, where: str) -> str:
    if not isinstance(v, str):
        actual = type(v).__name__ if v is not None else "missing"
        msg = f"profile: {where} must be a string, got {actual}"
        raise ValueError(msg)
    return v


def get_int(data: dict[str, TomlValue], key: str, where: str) -> int:
    v = data.get(key)
    if isinstance(v, bool):  # bool is a subclass of int, but we don't want to allow it
        actual = type(v).__name__
        msg = f"profile: {where}.{key} must be an integer, got {actual}"
        raise ValueError(msg)
    if not isinstance(v, int):
        actual = type(v).__name__ if v is not None else "missing"
        msg = f"profile: {where} must be an integer, got {actual}"
        raise ValueError(msg)
    return v


def get_float(data: dict[str, TomlValue], key: str, where: str) -> float:
    v = data.get(key)
    if not isinstance(v, (int, float)):
        actual = type(v).__name__ if v is not None else "missing"
        msg = f"profile: {where} must be a number, got {actual}"
        raise ValueError(msg)
    return float(v)
