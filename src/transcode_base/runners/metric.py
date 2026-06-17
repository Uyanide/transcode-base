"""Quality metric tasks."""

from __future__ import annotations

import json
import math
import re
import statistics
from pathlib import Path
from typing import ClassVar, Protocol, cast

from attrs import define, frozen

from .base import ShellRunResult, shell

__all__ = [
    "PSNR",
    "SSIM",
    "SSIMULACRA2",
    "VMAF",
    "VMAFCUDA",
    "XPSNR",
    "METRICS",
    "Butteraugli",
    "ButteraugliResult",
    "ChannelStats",
    "MetricRunner",
    "PSNRResult",
    "SSIMResult",
    "SSIMULACRA2Result",
    "VMAFResult",
    "XPSNRResult",
]


@frozen
class ChannelStats:
    mean: float
    harmonic_mean: float
    std: float
    median: float
    p5: float
    p95: float
    min: float
    max: float


@frozen
class _MetricResult:
    reference: Path
    distorted: Path
    shell: ShellRunResult


@frozen
class _LogMetricResult(_MetricResult):
    log_path: Path
    channels: dict[str, ChannelStats]

    def _stat_items(self, ch: ChannelStats) -> list[tuple[str, float]]:
        """Aggregates that are meaningful for this metric, as (label, value) pairs.

        ``p5``  — worst 5 % for higher-is-better metrics (SSIM, PSNR, VMAF, SSIMULACRA2).
        ``p95`` — worst 5 % for lower-is-better metrics (Butteraugli).
        ``harmonic_mean`` — industry standard for VMAF;
                            for PSNR, frames with infinite PSNR are excluded from the
                            reciprocal sum so they do not artificially inflate the result;
                            for Butteraugli, this is computed but not meaningful.
        """
        return [
            ("mean", ch.mean),
            ("hmean", ch.harmonic_mean),
            ("std", ch.std),
            ("median", ch.median),
            ("p5", ch.p5),
            ("min", ch.min),
            ("max", ch.max),
        ]

    def print_channels(self) -> None:
        for name, ch in self.channels.items():
            body = "  ".join(f"{label}={value:.4f}" for label, value in self._stat_items(ch))
            print(f"{name}:  {body}")


@frozen
class VMAFResult(_LogMetricResult):
    pass


@frozen
class SSIMResult(_LogMetricResult):
    pass


@frozen
class PSNRResult(_LogMetricResult):
    pass


@frozen
class XPSNRResult(_LogMetricResult):
    pass


@frozen
class SSIMULACRA2Result(_LogMetricResult):
    pass


@frozen
class ButteraugliResult(_LogMetricResult):
    def _stat_items(self, ch: ChannelStats) -> list[tuple[str, float]]:
        # lower-is-better: worst 5 % is the high tail (p95); harmonic mean not meaningful
        return [
            ("mean", ch.mean),
            ("std", ch.std),
            ("median", ch.median),
            ("p95", ch.p95),
            ("min", ch.min),
            ("max", ch.max),
        ]


@define
class _FFmpegStatsRunner[Result: _LogMetricResult]:
    """Base for ffmpeg metric runners that write a per-frame stats file."""

    filter_name: ClassVar[str]  # "ssim" / "psnr" / "xpsnr"
    log_suffix: ClassVar[str]  # ".ssim.txt" / ".psnr.txt" / ".xpsnr.txt"
    output_suffix: ClassVar[str] = ".txt"
    result_cls: ClassVar[type[_LogMetricResult]]

    reference: Path
    distorted: Path

    threads: int | None = None
    every: int | None = None
    log_path: Path | None = None

    reference_filters: list[str] | None = None
    distorted_filters: list[str] | None = None

    def _resolved_log_path(self) -> Path:
        return self.log_path or _build_log_path(self.distorted, self.log_suffix)

    def build_cmd(self) -> list[str]:
        log = self._resolved_log_path()
        return _build_ffmpeg_filter_cmd(
            self.reference,
            self.distorted,
            distorted_filters=self.distorted_filters,
            reference_filters=self.reference_filters,
            metric_filter=f"{self.filter_name}=stats_file={_escape_filter_arg(str(log))}",
            every=self.every,
            threads=self.threads,
        )

    def _parse_log(self, path: Path) -> dict[str, list[float]]: ...

    def run(self) -> Result:
        log = self._resolved_log_path()
        shell_result = shell(self.build_cmd())
        if not log.exists():
            msg = f"{self.filter_name} stats file not found at {log}"
            raise RuntimeError(msg)
        per_channel = self._parse_log(log)
        channels = {name: _aggregate(values) for name, values in per_channel.items()}
        return cast(
            Result,
            self.result_cls(
                reference=self.reference,
                distorted=self.distorted,
                shell=shell_result,
                log_path=log,
                channels=channels,
            ),
        )


@define
class SSIM(_FFmpegStatsRunner[SSIMResult]):
    filter_name = "ssim"
    log_suffix = ".ssim.txt"
    result_cls = SSIMResult

    def _parse_log(self, path: Path) -> dict[str, list[float]]:
        return _parse_ssim_stats(path)


@define
class PSNR(_FFmpegStatsRunner[PSNRResult]):
    filter_name = "psnr"
    log_suffix = ".psnr.txt"
    result_cls = PSNRResult

    def _parse_log(self, path: Path) -> dict[str, list[float]]:
        return _parse_psnr_stats(path)


@define
class XPSNR(_FFmpegStatsRunner[XPSNRResult]):
    filter_name = "xpsnr"
    log_suffix = ".xpsnr.txt"
    result_cls = XPSNRResult

    def _parse_log(self, path: Path) -> dict[str, list[float]]:
        return _parse_xpsnr_stats(path)


@define
class VMAF:
    output_suffix: ClassVar[str] = ".json"

    reference: Path
    distorted: Path

    threads: int | None = None
    every: int | None = None
    model: str | None = None  # VMAF model version
    log_path: Path | None = None

    reference_filters: list[str] | None = None
    distorted_filters: list[str] | None = None

    use_cuda: bool = False

    def __attrs_post_init__(self) -> None:
        if not self.use_cuda:
            return

        self.reference_filters = (self.reference_filters or []) + ["scale_cuda=format=yuv420p"]
        self.distorted_filters = (self.distorted_filters or []) + ["scale_cuda=format=yuv420p"]

    def _resolved_log_path(self) -> Path:
        return self.log_path or _build_log_path(self.distorted, ".vmaf.json")

    def build_cmd(self) -> list[str]:
        log = self._resolved_log_path()
        opts = [f"log_path={_escape_filter_arg(str(log))}", "log_fmt=json"]
        if self.threads is not None:
            # This is expected to fail on libvmaf_cuda. but who knows, maybe it
            # will be supported in the future?
            opts.append(f"n_threads={self.threads}")
        if self.every is not None:
            opts.append(f"n_subsample={self.every}")
        if self.model is not None:
            opts.append(f"model=version={self.model}")
        if self.use_cuda:
            libvmaf = "libvmaf_cuda=" + ":".join(opts)
        else:
            libvmaf = "libvmaf=" + ":".join(opts)
        return _build_ffmpeg_filter_cmd(
            self.distorted,  # libvmaf expects distorted first, then reference
            self.reference,  # while the others (xpsnr) expect the opposite
            distorted_filters=self.reference_filters,
            reference_filters=self.distorted_filters,
            metric_filter=libvmaf,
            every=None,  # handled in metric_filter
            cuda_input=self.use_cuda,
            # threads=None,  # handled in metric_filter
        )

    def run(self) -> VMAFResult:
        log = self._resolved_log_path()
        shell_result = shell(self.build_cmd())
        if not log.exists():
            msg = f"VMAF log file not found at {log}"
            raise RuntimeError(msg)
        try:
            data = json.loads(log.read_text())
            frames = [float(f["metrics"]["vmaf"]) for f in data["frames"]]
            return VMAFResult(
                reference=self.reference,
                distorted=self.distorted,
                shell=shell_result,
                log_path=log,
                channels={"vmaf": _aggregate(frames)},
            )
        except (KeyError, TypeError, ValueError) as e:
            msg = f"unexpected libvmaf JSON shape at {log}: {e}"
            raise RuntimeError(msg) from e


@define
class VMAFCUDA(VMAF):
    use_cuda: bool = True


@define
class _FFVshipRunner[Result: _LogMetricResult]:
    metric_arg: ClassVar[str]
    metric_name: ClassVar[str]
    output_suffix: ClassVar[str] = ".json"
    result_cls: ClassVar[type[_LogMetricResult]]

    reference: Path
    distorted: Path

    threads: int | None = None
    every: int | None = None
    log_path: Path | None = None

    def _resolved_log_path(self) -> Path:
        return self.log_path or _build_log_path(self.distorted, f".{self.metric_name.lower()}.json")

    def _column_names(self, width: int) -> list[str]:
        """Return channel names for *width* FFVship columns.

        Override in subclasses that have fixed, named columns (e.g. Butteraugli).
        """
        if width == 1:
            return [self.metric_name]
        return [f"{self.metric_name}[{i}]" for i in range(width)]

    def build_cmd(self) -> list[str]:
        log = self._resolved_log_path()
        return _build_ffvship_cmd(
            self.reference,
            self.distorted,
            self.metric_arg,
            self.threads,
            self.every,
            log,
        )

    def run(self) -> Result:
        log = self._resolved_log_path()
        shell_result = shell(self.build_cmd())
        if not log.exists():
            msg = f"{self.metric_name} log file not found at {log}"
            raise RuntimeError(msg)
        rows = _ffvship_load_rows(log)
        width = len(rows[0])
        names = self._column_names(width)
        channels = {name: _aggregate([row[i] for row in rows]) for i, name in enumerate(names)}
        return cast(
            Result,
            self.result_cls(
                reference=self.reference,
                distorted=self.distorted,
                shell=shell_result,
                log_path=log,
                channels=channels,
            ),
        )


@define
class SSIMULACRA2(_FFVshipRunner[SSIMULACRA2Result]):
    metric_arg = "ssimulacra2"
    metric_name = "SSIMULACRA2"
    result_cls = SSIMULACRA2Result


@define
class Butteraugli(_FFVshipRunner[ButteraugliResult]):
    metric_arg = "butteraugli"
    metric_name = "Butteraugli"
    result_cls = ButteraugliResult

    def _column_names(self, width: int) -> list[str]:
        if width == 3:
            return ["2-Norm", "3-Norm", "INF-Norm"]
        return super()._column_names(width)


class MetricRunner(Protocol):
    """The common surface every metric runner exposes"""

    output_suffix: ClassVar[str]

    def __init__(
        self,
        *,
        reference: Path,
        distorted: Path,
        threads: int | None = None,
        every: int | None = None,
        log_path: Path | None = None,
    ) -> None: ...

    def build_cmd(self) -> list[str]: ...

    def run(self) -> _LogMetricResult: ...


METRICS: dict[str, type[MetricRunner]] = {
    "ssim": SSIM,
    "psnr": PSNR,
    "xpsnr": XPSNR,
    "vmaf": VMAF,
    "vmafcuda": VMAFCUDA,
    "ssimulacra2": SSIMULACRA2,
    "butteraugli": Butteraugli,
}


def _escape_filter_arg(s: str) -> str:
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def _build_ffmpeg_filter_cmd(
    reference: Path,
    distorted: Path,
    metric_filter: str,
    *,
    distorted_filters: list[str] | None = None,
    reference_filters: list[str] | None = None,
    every: int | None = None,
    threads: int | None = None,
    cuda_input: bool = False,
) -> list[str]:
    distorted_filters = [
        f
        for f in (distorted_filters or [])
        if not (f.startswith("settb=") or f.startswith("setpts="))
    ]
    reference_filters = [
        f
        for f in (reference_filters or [])
        if not (f.startswith("settb=") or f.startswith("setpts="))
    ]
    if every is not None and every > 1:
        distorted_filters.append(f"framestep={every}")
        reference_filters.append(f"framestep={every}")
    distorted_filters.extend(["settb=AVTB", "setpts=PTS-STARTPTS"])
    reference_filters.extend(["settb=AVTB", "setpts=PTS-STARTPTS"])
    filtergraph = ""
    filtergraph += f"[0:v]{','.join(distorted_filters)}[d];"
    filtergraph += f"[1:v]{','.join(reference_filters)}[r];"
    filtergraph += f"[r][d]{metric_filter}"
    cmd = [
        "ffmpeg",
        "-hide_banner",
    ]

    if cuda_input:
        cmd.extend(
            [
                "-hwaccel",
                "cuda",
                "-hwaccel_output_format",
                "cuda",
                "-i",
                str(distorted),
                "-hwaccel",
                "cuda",
                "-hwaccel_output_format",
                "cuda",
                "-i",
                str(reference),
            ]
        )
    else:
        cmd.extend(
            [
                "-i",
                str(distorted),
                "-i",
                str(reference),
            ]
        )

    cmd.extend(
        [
            "-an",
            "-sn",
            "-filter_complex",
            filtergraph,
        ]
    )
    # -filter_threads parallelises slice-threaded filters; its benefit for ssim/psnr
    # is marginal (libvmaf has its own n_threads), but it keeps the surface uniform.
    if threads is not None:
        cmd.extend(["-filter_threads", str(threads)])
    cmd.extend(["-f", "null", "-"])
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


def _build_log_path(base: Path, suffix: str) -> Path:
    return base.with_suffix(suffix)


def _parse_ssim_stats(path: Path) -> dict[str, list[float]]:
    """Parse an ffmpeg ssim stats file into per-channel per-frame value lists.

    Line format::

        n:1 Y:0.999999 U:0.999992 V:0.999994 All:0.999997 (55.23)

    Returns keys: ``Y``, ``U``, ``V``, ``All``.
    """
    result: dict[str, list[float]] = {}
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for m in re.finditer(r"\b(Y|U|V|All):([\d.]+)", line):
                result.setdefault(m.group(1), []).append(float(m.group(2)))
    if not result:
        msg = f"SSIM stats file at {path} contains no data"
        raise RuntimeError(msg)
    return result


_PSNR_KEY_MAP = {"psnr_y": "Y", "psnr_u": "U", "psnr_v": "V", "psnr_avg": "All"}


def _parse_psnr_stats(path: Path) -> dict[str, list[float]]:
    """Parse an ffmpeg psnr stats file into per-channel per-frame value lists.

    Line format::

        n:1 mse_avg:0.018 mse_y:0.024 mse_u:0.018 mse_v:0.014
            psnr_avg:65.52 psnr_y:64.25 psnr_u:65.51 psnr_v:66.69

    Returns keys: ``Y``, ``U``, ``V``, ``All``.
    Handles ``inf`` values (frames identical to reference have infinite PSNR).
    """
    result: dict[str, list[float]] = {}
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for ffmpeg_key, channel in _PSNR_KEY_MAP.items():
                m = re.search(rf"\b{ffmpeg_key}:(inf|\d+(?:\.\d+)?)", line)
                if m:
                    result.setdefault(channel, []).append(float(m.group(1)))
    if not result:
        msg = f"PSNR stats file at {path} contains no data"
        raise RuntimeError(msg)
    return result


def _parse_xpsnr_stats(path: Path) -> dict[str, list[float]]:
    """Parse an ffmpeg xpsnr stats file into per-channel per-frame value lists.

    Line format::

        n:    1  XPSNR y: 48.6592  XPSNR u: 54.6191  XPSNR v: 54.7136

    Returns keys: ``Y``, ``U``, ``V``.
    """
    result: dict[str, list[float]] = {}
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for m in re.finditer(r"\bXPSNR\s+([yuv]):\s*(\d+(?:\.\d+)?)", line):
                channel = m.group(1).upper()
                result.setdefault(channel, []).append(float(m.group(2)))
    if not result:
        msg = f"XPSNR stats file at {path} contains no data"
        raise RuntimeError(msg)
    return result


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


def _aggregate(values: list[float]) -> ChannelStats:
    """Aggregate per-frame values into a :class:`ChannelStats`."""
    n = len(values)
    if n == 0:
        msg = "cannot aggregate an empty value list"
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

    # Harmonic mean over finite positive values only.
    # ∞-PSNR frames (identical to reference) are excluded so they do not
    # interfere with the reciprocal sum; VMAF/SSIM values are always finite.
    finite_pos = [v for v in values if math.isfinite(v) and v > 0]
    harmonic_mean = statistics.harmonic_mean(finite_pos) if finite_pos else 0.0

    return ChannelStats(
        mean=statistics.mean(values),
        harmonic_mean=harmonic_mean,
        std=statistics.stdev(values) if n >= 2 else 0.0,
        median=statistics.median(values),
        p5=pct(5),
        p95=pct(95),
        min=ordered[0],
        max=ordered[-1],
    )
