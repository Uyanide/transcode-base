from __future__ import annotations

import argparse
import shlex
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..runners.metric import METRICS
from ._utils import existing_file, positive_int


def main() -> None:
    p = argparse.ArgumentParser(description="Measure video quality (reference vs. distorted).")
    p.add_argument("reference", type=existing_file)
    p.add_argument("distorted", type=existing_file)
    p.add_argument("type", choices=sorted(METRICS))
    p.add_argument("--threads", type=positive_int)
    p.add_argument("--every", type=positive_int)
    p.add_argument("--dry-run", action="store_true")
    ns = p.parse_args()

    runner_cls = METRICS[ns.type]
    with NamedTemporaryFile(suffix=runner_cls.output_suffix) as tmp:
        runner = runner_cls(
            reference=ns.reference,
            distorted=ns.distorted,
            threads=ns.threads,
            every=ns.every,
            log_path=Path(tmp.name),
        )
        if ns.dry_run:
            print(shlex.join(runner.build_cmd()))
            return
        runner.run().print_channels()
