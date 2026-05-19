from __future__ import annotations

import argparse


def kv_type(s: str) -> tuple[str, str]:
    """argparse ``type=`` for KEY=VALUE arguments."""
    if "=" not in s:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {s!r}")
    k, _, v = s.partition("=")
    return k, v
