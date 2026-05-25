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


def shell(
    cmd: list[str],
    *,
    check: bool = True,
    stdout: bool = False,
    stderr: bool = False,
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
