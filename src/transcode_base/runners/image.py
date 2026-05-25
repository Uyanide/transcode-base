"""Image-encoding task."""

from __future__ import annotations

import shutil
from pathlib import Path

from attr import define, frozen

from ..profiles.image import BackendProfile, Profile
from ..utils import render
from .base import ShellRunResult, shell

__all__ = [
    "Image",
    "Profile",
    "Result",
]


@frozen
class Result:
    input: Path
    output: Path
    shell: ShellRunResult


@define
class Image:
    input: Path
    output: Path
    profile: Profile
    format: str
    backend: str

    def build_cmd(self) -> list[str]:
        backend_cfg = _select_backend(self.profile, self.format, self.backend)
        if shutil.which(backend_cfg.requires) is None:
            msg = (
                f"image encoder {self.backend!r} requires {backend_cfg.requires!r},"
                " which was not found on PATH"
            )
            raise RuntimeError(msg)
        ctx = dict(backend_cfg.args)
        ctx["input_path"] = str(self.input)
        ctx["output_path"] = str(self.output)
        return [render(token, ctx) for token in backend_cfg.command]

    def run(self) -> Result:
        result = shell(self.build_cmd())
        return Result(input=self.input, output=self.output, shell=result)


def _select_backend(profile: Profile, format: str, backend: str) -> BackendProfile:
    formats = profile.formats
    if format not in formats:
        available = ", ".join(sorted(formats)) or "<none>"
        msg = f"unknown image format {format!r}; available: {available}"
        raise KeyError(msg)
    backends = formats[format]
    if backend not in backends:
        available = ", ".join(sorted(backends)) or "<none>"
        msg = f"unknown image backend {format!r}.{backend!r}; available: {available}"
        raise KeyError(msg)
    return backends[backend]
