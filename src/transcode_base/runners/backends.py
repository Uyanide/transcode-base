"""Built-in ShellBackend implementations."""

from __future__ import annotations

import shlex
import subprocess
import time
from typing import Callable

from attrs import frozen

from .base import ShellBackend, ShellRunResult, default_backend

__all__ = [
    "LoggingBackend",
    "QuietBackend",
    "TimedBackend",
    "TimedShellRunResult",
]


@frozen
class TimedShellRunResult(ShellRunResult):
    elapsed: float  # seconds


class QuietBackend:
    def __call__(
        self, cmd: list[str], *, check: bool, stdout: bool, stderr: bool
    ) -> ShellRunResult:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE if stdout else subprocess.DEVNULL,
            stderr=subprocess.PIPE if stderr else subprocess.DEVNULL,
            check=check,
        )
        return ShellRunResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            cmd=cmd,
        )


class TimedBackend:
    def __init__(self, inner: ShellBackend = default_backend) -> None:
        self._inner = inner
        self.timings: list[TimedShellRunResult] = []

    def __call__(
        self, cmd: list[str], *, check: bool, stdout: bool, stderr: bool
    ) -> TimedShellRunResult:
        t0 = time.perf_counter()
        result = self._inner(cmd, check=check, stdout=stdout, stderr=stderr)
        elapsed = time.perf_counter() - t0
        timed = TimedShellRunResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            cmd=result.cmd,
            elapsed=elapsed,
        )
        self.timings.append(timed)
        return timed


class LoggingBackend:
    def __init__(
        self,
        inner: ShellBackend = default_backend,
        *,
        log: Callable[[str], None] = print,
    ) -> None:
        self._inner = inner
        self._log = log

    def __call__(
        self, cmd: list[str], *, check: bool, stdout: bool, stderr: bool
    ) -> ShellRunResult:
        self._log(f"$ {shlex.join(cmd)}")
        result = self._inner(cmd, check=check, stdout=stdout, stderr=stderr)
        self._log(f"  → {result.returncode}")
        return result
