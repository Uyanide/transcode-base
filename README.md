# transcode-base

> What were the parameters I used to encode that similar video a week ago🤔
>
> Oh, shell history, I see. But, what makes it better is a ...

Profile-based wrappers for video / audio / image encoding and quality measurement.

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

# load defaults and override one encoder key
profile = tb.load_profile(tb.av1an.Profile, {"tq": {"svt-av1": {"args": {"preset": "6"}}}})

result = tb.av1an.Av1an(
    input=Path("input.mkv"),
    output=Path("output.mkv"),
    profile=profile,
    mode=tb.av1an.Mode.TQ,
    encoder="svt-av1",
    audio="libopus",
).run()
```

### Shell backends

By default runners execute commands directly. Use `use_backend` to inject
alternative behaviour for the duration of a `with` block:

```python
import transcode_base as tb

# suppress terminal output
with tb.use_backend(tb.QuietBackend()):
    runner.run()

# measure time per command
timed = tb.TimedBackend()
with tb.use_backend(timed):
    runner.run()
for t in timed.timings:
    print(f"{t.elapsed:.3f}s  {t.cmd[0]}")

# log commands (stack on top of the current backend)
with tb.use_backend(tb.LoggingBackend(inner=tb.current_backend())):
    runner.run()
```

## CLI

### av1an

```sh
tb-av input.mkv
tb-av input.mkv -o out.mkv --video svt-av1 --audio libfdk_aac --mode tq
```

`--arg KEY=VALUE` overrides individual keys in the encoder's `args` render context; `--probe KEY=VALUE` overrides the probe context.

### Encode with ffmpeg (single-pass)

```sh
tb-ff input.mkv
tb-ff input.mkv --video libx265 --audio libopus --arg crf=20
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
