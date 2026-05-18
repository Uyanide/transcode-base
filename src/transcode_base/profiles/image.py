"""Typed profile for the image-encoding subsystem.

Mirrors `image.toml`:

    [<format>.<backend>]
        requires = "<executable>"
        command  = ["argv0", "...{{ var }}..."]
        args     = { speed = "...", quality = "..." }

The `command` list is the full argv template; `args` plus the implicit
`{input_path, output_path}` form the render context.
"""

from __future__ import annotations

from attrs import frozen

from .base import RawProfile, TomlValue, get_str


@frozen
class BackendProfile:
    requires: str  # executable name to check via shutil.which
    command: list[str]  # argv template with {{ var }} placeholders
    args: dict[str, str]  # render context (speed, quality, ...)


@frozen
class Profile:
    formats: dict[str, dict[str, BackendProfile]]  # format -> backend -> ImageBackend

    @classmethod
    def from_raw(cls, raw: RawProfile) -> Profile:
        formats: dict[str, dict[str, BackendProfile]] = {}
        for fmt_name, fmt_data in raw.items():
            if not isinstance(fmt_data, dict):
                msg = f"image profile: {fmt_name!r} must be a table"
                raise ValueError(msg)
            backends: dict[str, BackendProfile] = {}
            for backend_name, backend_data in fmt_data.items():
                backends[backend_name] = _parse_backend(backend_data, f"{fmt_name}.{backend_name}")
            formats[fmt_name] = backends
        return cls(formats=formats)

    @staticmethod
    def default_name() -> str:
        return "image"


def _parse_backend(data: TomlValue, where: str) -> BackendProfile:
    if not isinstance(data, dict):
        msg = f"image profile: {where!r} must be a table"
        raise ValueError(msg)
    requires = get_str(data, "requires", where)
    command_raw = data.get("command")
    if not isinstance(command_raw, list):
        msg = f"image profile: {where}.command must be a list of strings"
        raise ValueError(msg)
    command: list[str] = []
    for i, item in enumerate(command_raw):
        if not isinstance(item, str):
            msg = f"image profile: {where}.command[{i}] must be a string"
            raise ValueError(msg)
        command.append(item)
    args_raw = data.get("args", {})
    if not isinstance(args_raw, dict):
        msg = f"image profile: {where}.args must be a table"
        raise ValueError(msg)
    args: dict[str, str] = {}
    for k, v in args_raw.items():
        if not isinstance(v, str):
            msg = f"image profile: {where}.args.{k} must be a string"
            raise ValueError(msg)
        args[k] = v
    return BackendProfile(requires=requires, command=command, args=args)
