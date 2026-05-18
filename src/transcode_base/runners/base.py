import subprocess
from typing import Protocol

from attrs import frozen


class Runnable[R](Protocol):
    def run(self) -> R: ...


@frozen
class ShellRunResult:
    returncode: int
    stdout: bytes | None
    stderr: bytes | None
    cmd: list[str]


def shell(cmd: list[str], *, check: bool = True, capture: bool = False) -> ShellRunResult:
    proc = subprocess.run(cmd, capture_output=capture, check=check)
    return ShellRunResult(
        returncode=proc.returncode,
        stdout=proc.stdout if capture else None,
        stderr=proc.stderr if capture else None,
        cmd=cmd,
    )
