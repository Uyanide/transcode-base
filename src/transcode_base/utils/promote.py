import attrs


def promote[R](src: object, cls: type[R], **extra) -> R:
    base = {f.name: getattr(src, f.name) for f in attrs.fields(type(src))}
    return cls(**base, **extra)
