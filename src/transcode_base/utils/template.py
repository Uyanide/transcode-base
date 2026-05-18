import re

_TOKEN = re.compile(r"\{\{\s*([\w-]+)\s*\}\}")


def render(template: str, ctx: dict[str, str]) -> str:
    """Substitute every {{ var }} token with ctx[var]. Missing variables raise KeyError."""

    def sub(m: re.Match[str]) -> str:
        return ctx[m.group(1)]

    return _TOKEN.sub(sub, template)
