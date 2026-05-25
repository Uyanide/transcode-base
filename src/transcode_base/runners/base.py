from __future__ import annotations

import subprocess
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Protocol

from attrs import frozen


class Runnable[R](Protocol):
    def run(self) -> R: ...


@frozen
class ShellRunResult:
    returncode: int
    stdout: bytes | None
    stderr: bytes | None
    cmd: list[str]


class ShellBackend(Protocol):
    def __call__(
        self,
        cmd: list[str],
        *,
        check: bool,
        stdout: bool,
        stderr: bool,
    ) -> ShellRunResult: ...


def default_backend(
    cmd: list[str], *, check: bool, stdout: bool, stderr: bool
) -> ShellRunResult:
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE if stdout else None,
        stderr=subprocess.PIPE if stderr else None,
        check=check,
    )
    return ShellRunResult(
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmd=cmd,
    )


_shell_backend: ContextVar[ShellBackend] = ContextVar(
    "shell_backend", default=default_backend
)


def current_backend() -> ShellBackend:
    """Return the backend active in the current context."""
    return _shell_backend.get()


@contextmanager
def use_backend(backend: ShellBackend) -> Iterator[None]:
    """Activate *backend* for the duration of the ``with`` block."""
    token = _shell_backend.set(backend)
    try:
        yield
    finally:
        _shell_backend.reset(token)


def shell(
    cmd: list[str],
    *,
    check: bool = True,
    stdout: bool = False,
    stderr: bool = False,
) -> ShellRunResult:
    return _shell_backend.get()(cmd, check=check, stdout=stdout, stderr=stderr)
