from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path


def kv_type(s: str) -> tuple[str, str]:
    """argparse ``type=`` for KEY=VALUE arguments."""
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {s!r}")
    k, _, v = s.partition("=")
    return k, v


def existing_file(s: str) -> Path:
    """argparse ``type=`` that rejects paths which are not existing files."""
    p = Path(s)
    if not p.is_file():
        raise argparse.ArgumentTypeError(f"no such file: {s}")
    return p


def existing_dir(s: str) -> Path:
    """argparse ``type=`` that rejects paths which are not existing directories."""
    p = Path(s)
    if not p.is_dir():
        raise argparse.ArgumentTypeError(f"no such directory: {s}")
    return p


def positive_int(s: str) -> int:
    """argparse ``type=`` for strictly positive integers."""
    v = int(s)
    if v <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {v}")
    return v


def bounded_int(lo: int, hi: int) -> Callable[[str], int]:
    """Build an argparse ``type=`` that accepts integers in ``[lo, hi]``."""

    def parse(s: str) -> int:
        v = int(s)
        if not lo <= v <= hi:
            raise argparse.ArgumentTypeError(f"must be in [{lo}, {hi}], got {v}")
        return v

    return parse
