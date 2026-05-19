# transcode-base

Personal toolkit for video / audio / image encoding and quality measurement. Typed Python wrappers around ffmpeg, av1an, ffprobe, and FFVship, plus CLI scripts for common tasks.

## What it is

A library (`transcode_base`) that models encoding jobs as frozen dataclasses: a **profile** (loaded from TOML, deep-merged with any overrides) drives a **runner** (builds and executes the CLI command, returns a typed result). No subprocess strings, no hidden global state.

Profiles live in `src/transcode_base/defaults/` and can be layered — pass extra TOML files or dicts to `load_profile()` and only the keys you specify change.

## Dependencies

- Python 3.13+, `attrs`
- External binaries (only what you actually use): `ffmpeg`, `ffprobe`, `av1an`, `FFVship`, `notify-send`, `oavif`, `avifenc`, `magick`, ...

## Library usage

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["transcode-base"]
#
# [tool.uv.sources]
# transcode-base = { path = "/path/to/transcode-base", editable = true }
# ///

from pathlib import Path
import transcode_base as tb
from transcode_base import load_profile

# load defaults and override one encoder key
profile = load_profile(tb.av1an.Profile, {"tq": {"svt-av1": {"args": {"preset": "6"}}}})

result = tb.av1an.Av1an(
    input=Path("input.mkv"),
    output=Path("output.mkv"),
    profile=profile,
    mode=tb.av1an.Mode.TQ,
    encoder="svt-av1",
    audio="libopus",
).run()
```

## CLI

All scripts accept `--help`.

### Encode with av1an

```sh
tb-av input.mkv
tb-av input.mkv -o out.mkv --video svt-av1 --audio libopus --mode cq
tb-av input.mkv --arg preset=6 --probe preset=10
```

`--arg KEY=VALUE` overrides individual keys in the encoder's `args` render context; `--probe KEY=VALUE` overrides the probe context.

### Encode with ffmpeg (single-pass)

```sh
tb-ff input.mkv
tb-ff input.mkv --video libx265 --audio libopus --arg crf=20
tb-ff input.mkv --no-audio
```

### Encode an image

```sh
tb-img input.png output.avif --backend avifenc
tb-img input.png output.avif --backend avifenc --arg quality=85
```

Format is inferred from the output extension.

### Batch-encode images (incremental)

```sh
tb-imgs frames/ encoded/ --format avif --backend avifenc --workers 8
tb-imgs frames/ encoded/ --format avif --backend oavif --arg quality=90 --glob "*.png"
```

Skips files whose output is already newer than the input.

### Extract samples

```sh
tb-sample input.mkv samples/
tb-sample input.mkv samples/ --count-scene 5 --count-uniform 8 --duration 15
```

Runs scene-change detection then extracts lossless FFV1 clips in parallel.

### Measure quality

```sh
tb-metric ref.mkv dist.mkv ssim
tb-metric ref.mkv dist.mkv vmaf --threads 8 --every 2
tb-metric ref.mkv dist.mkv ssimulacra2
tb-metric ref.mkv dist.mkv butteraugli --every 4
```
