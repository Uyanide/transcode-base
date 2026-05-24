"""Quality metric tasks."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import ClassVar, cast

from attr import define, frozen

from ..utils import promote
from .base import ShellRunResult, shell

__all__ = [
    "PSNR",
    "SSIM",
    "SSIMULACRA2",
    "VMAF",
    "Butteraugli",
    "ButteraugliResult",
    "FFVshipChannel",
    "PSNRResult",
    "SSIMResult",
    "SSIMULACRA2Result",
    "VMAFResult",
]


@frozen
class _MetricResult(ShellRunResult):
    reference: Path
    distorted: Path


@frozen
class VMAFResult(_MetricResult):
    json_path: Path
    mean: float
    harmonic_mean: float
    min: float
    max: float


@frozen
class SSIMResult(_MetricResult):
    mean: float


@frozen
class PSNRResult(_MetricResult):
    y: float
    u: float
    v: float
    average: float
    min: float
    max: float


@frozen
class FFVshipChannel:
    name: str
    mean: float
    std: float
    median: float
    p5: float
    p95: float
    min: float
    max: float


@frozen
class _FFVshipMetricResult(_MetricResult):
    json_path: Path
    channels: list[FFVshipChannel]


@frozen
class SSIMULACRA2Result(_FFVshipMetricResult):
    pass


@frozen
class ButteraugliResult(SSIMULACRA2Result):
    pass


@define
class _FFmpegBaseRunner[Result: _MetricResult]:
    metric_name: ClassVar[str]
    metric_arg: ClassVar[str]
    result_cls: ClassVar[type[_MetricResult]]

    reference: Path
    distorted: Path
    reference_filters: list[str] | None = None
    distorted_filters: list[str] | None = None

    def parse(self, text: str) -> dict[str, float]: ...

    def build_cmd(self) -> list[str]:
        return _build_ffmpeg_filter_cmd(
            self.reference,
            self.distorted,
            distorted_filter=self.distorted_filters,
            reference_filter=self.reference_filters,
            metric_filter=self.metric_arg,
        )

    def run(self) -> Result:
        shell_result = shell(self.build_cmd(), capture=True)
        if shell_result.stderr is None:
            msg = (
                f"{self.metric_name} metric did not produce any stderr output for {self.distorted}"
            )
            raise RuntimeError(msg)
        return cast(
            Result,
            promote(
                shell_result,
                self.result_cls,
                reference=self.reference,
                distorted=self.distorted,
                **self.parse(shell_result.stderr.decode()),
            ),
        )


@define
class SSIM(_FFmpegBaseRunner[SSIMResult]):
    metric_name = "SSIM"
    metric_arg = "ssim"
    result_cls = SSIMResult

    def parse(self, text: str) -> dict[str, float]:
        m = re.search(r"\bAll:(\d+\.\d+)", text)
        if not m:
            msg = f"Failed to parse {self.metric_name} result from: {text}"
            raise RuntimeError(msg)
        return {"mean": float(m.group(1))}


@define
class PSNR(_FFmpegBaseRunner[PSNRResult]):
    metric_name = "PSNR"
    metric_arg = "psnr"
    result_cls = PSNRResult

    def parse(self, text: str) -> dict[str, float]:
        ret = {}
        for key in ["y", "u", "v", "average", "min", "max"]:
            m = re.search(rf"\b{key}:(\d+\.\d+)", text)
            if not m:
                msg = f"Failed to parse PSNR {key} from: {text}"
                raise RuntimeError(msg)
            ret[key] = float(m.group(1))
        return ret


@define
class VMAF:
    reference: Path
    distorted: Path

    threads: int | None = None
    subsample: int | None = None
    model: str | None = None  # VMAF model version, e.g. "vmaf_v0.6.1"
    log_path: Path | None = None
    reference_filters: list[str] | None = None
    distorted_filters: list[str] | None = None

    def build_cmd(self) -> list[str]:
        if self.log_path is None:
            self.log_path = _build_log_path(self.distorted, ".vmaf.json")

        opts = [f"log_path={self.log_path}", "log_fmt=json"]
        if self.threads is not None:
            opts.append(f"n_threads={self.threads}")
        if self.subsample is not None:
            opts.append(f"n_subsample={self.subsample}")
        if self.model is not None:
            opts.append(f"model=version={self.model}")
        libvmaf = "libvmaf=" + ":".join(opts)
        return _build_ffmpeg_filter_cmd(
            self.reference,
            self.distorted,
            distorted_filter=self.distorted_filters,
            reference_filter=self.reference_filters,
            metric_filter=libvmaf,
        )

    def run(self) -> VMAFResult:
        shell_result = shell(self.build_cmd())
        if self.log_path is None:
            msg = "log_path must be set to parse VMAF result"
            raise RuntimeError(msg)
        if not self.log_path.exists():
            msg = f"VMAF log file not found at {self.log_path}"
            raise RuntimeError(msg)
        try:
            data = json.loads(self.log_path.read_text())
            pooled = data["pooled_metrics"]["vmaf"]
            return promote(
                shell_result,
                VMAFResult,
                reference=self.reference,
                distorted=self.distorted,
                json_path=self.log_path,
                mean=float(pooled["mean"]),
                harmonic_mean=float(pooled["harmonic_mean"]),
                min=float(pooled["min"]),
                max=float(pooled["max"]),
            )
        except (KeyError, TypeError, ValueError) as e:
            msg = f"unexpected libvmaf JSON shape at {self.log_path}: {e}"
            raise RuntimeError(msg) from e


@define
class _FFVshipRunner:
    metric_arg: ClassVar[str]
    metric_name: ClassVar[str]

    reference: Path
    distorted: Path
    threads: int | None = None
    every: int | None = None
    log_path: Path | None = None

    def build_cmd(self) -> list[str]:
        if self.log_path is None:
            self.log_path = _build_log_path(self.distorted, f".{self.metric_name}.json")
        return _build_ffvship_cmd(
            self.reference,
            self.distorted,
            self.metric_arg,
            self.threads,
            self.every,
            self.log_path,
        )

    def run(self) -> _FFVshipMetricResult:
        shell_result = shell(self.build_cmd())
        if self.log_path is None:
            msg = f"log_path must be set to parse {self.metric_name} result"
            raise RuntimeError(msg)
        if not self.log_path.exists():
            msg = f"{self.metric_name} log file not found at {self.log_path}"
            raise RuntimeError(msg)
        rows = _ffvship_load_rows(self.log_path)
        return promote(
            shell_result,
            _FFVshipMetricResult,
            reference=self.reference,
            distorted=self.distorted,
            json_path=self.log_path,
            channels=_aggregate_columns(rows, self.metric_name),
        )


@define
class SSIMULACRA2(_FFVshipRunner):
    metric_arg = "ssimulacra2"
    metric_name = "SSIMULACRA2"


@define
class Butteraugli(_FFVshipRunner):
    metric_arg = "butteraugli"
    metric_name = "Butteraugli"


def _build_ffmpeg_filter_cmd(
    reference: Path,
    distorted: Path,
    distorted_filter: list[str] | None = None,
    reference_filter: list[str] | None = None,
    metric_filter: str = "",
) -> list[str]:
    filtergraph = ""
    distorted_filter = [
        f
        for f in (distorted_filter or [])
        if not (f.startswith("settb=") or f.startswith("setpts="))
    ]
    reference_filter = [
        f
        for f in (reference_filter or [])
        if not (f.startswith("settb=") or f.startswith("setpts="))
    ]
    distorted_filter.extend(["settb=AVTB", "setpts=PTS-STARTPTS"])
    reference_filter.extend(["settb=AVTB", "setpts=PTS-STARTPTS"])
    filtergraph += f"[0:v]{','.join(distorted_filter)}[d];"
    filtergraph += f"[1:v]{','.join(reference_filter)}[r];"
    filtergraph += f"[d][r]{metric_filter}"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(distorted),
        "-i",
        str(reference),
        "-filter_complex",
        filtergraph,
        "-f",
        "null",
        "-",
    ]
    return cmd


def _build_ffvship_cmd(
    reference: Path,
    distorted: Path,
    metric: str,
    threads: int | None,
    every: int | None,
    log_path: Path,
) -> list[str]:
    cmd = [
        "FFVship",
        "--source",
        str(reference),
        "--encoded",
        str(distorted),
        "--metric",
        metric,
        "--json",
        str(log_path),
    ]
    if threads is not None:
        cmd.extend(["--threads", str(threads)])
    if every is not None:
        cmd.extend(["--every", str(every)])
    return cmd


def _ffvship_load_rows(json_path: Path) -> list[list[float]]:
    """FFVship's JSON is a list of per-frame rows, each a list of floats.
    SSIMULACRA2 produces 1 column; Butteraugli produces 3 (2-Norm, 3-Norm, INF-Norm)."""
    data = json.loads(json_path.read_text())
    if not isinstance(data, list) or not data:
        msg = f"FFVship JSON at {json_path} should be a non-empty list"
        raise RuntimeError(msg)
    rows: list[list[float]] = []
    for i, row in enumerate(data):
        if not isinstance(row, list) or not row:
            msg = f"FFVship JSON row {i}: expected non-empty list, got {row!r}"
            raise RuntimeError(msg)
        floats: list[float] = []
        for v in row:
            if not isinstance(v, int | float):
                msg = f"FFVship JSON row {i}: non-numeric value {v!r}"
                raise RuntimeError(msg)
            floats.append(float(v))
        rows.append(floats)
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        msg = "FFVship JSON: per-frame rows have inconsistent length"
        raise RuntimeError(msg)
    return rows


def _aggregate_columns(rows: list[list[float]], metric: str) -> list[FFVshipChannel]:
    width = len(rows[0])
    names = _channel_names(metric, width)
    return [_aggregate_column(name, [r[i] for r in rows]) for i, name in enumerate(names)]


def _channel_names(metric: str, width: int) -> list[str]:
    """Match FFVship's stdout section labels where we can; fall back to indexed names."""
    if metric == "Butteraugli" and width == 3:
        return ["Butteraugli 2-Norm", "Butteraugli 3-Norm", "Butteraugli INF-Norm"]
    if width == 1:
        return [metric]
    return [f"{metric}[{i}]" for i in range(width)]


def _aggregate_column(name: str, values: list[float]) -> FFVshipChannel:
    """Compute the seven aggregates FFVship's stdout shows. Linear interpolation
    for percentiles (matches numpy's default, well-defined for any n >= 1)."""
    n = len(values)
    if n == 0:
        msg = f"FFVship channel {name!r}: empty value list"
        raise RuntimeError(msg)
    ordered = sorted(values)

    def pct(p: float) -> float:
        if n == 1:
            return ordered[0]
        rank = p / 100 * (n - 1)
        lo = int(rank)
        hi = min(lo + 1, n - 1)
        frac = rank - lo
        return ordered[lo] * (1 - frac) + ordered[hi] * frac

    return FFVshipChannel(
        name=name,
        mean=sum(values) / n,
        std=statistics.stdev(values) if n >= 2 else 0.0,
        median=statistics.median(values),
        p5=pct(5),
        p95=pct(95),
        min=ordered[0],
        max=ordered[-1],
    )


def _build_log_path(base: Path, suffix: str) -> Path:
    return base.with_suffix(suffix)
