"""Hassfest utils."""
from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
import shutil
import subprocess
from typing import Any

DEFAULT_GENERATOR = "script.hassfest"


def _wrap_items(
    items: Iterable[str],
    opener: str,
    closer: str,
    sort: bool = False,
) -> str:
    """Wrap pre-formatted Python reprs in braces, optionally sorting them."""
    # The trailing comma is imperative so Black doesn't format some items
    # on one line and some on multiple.
    if sort:
        items = sorted(items)

    joined_items = ", ".join(items)
    return f"{opener}{joined_items}{',' if joined_items else ''}{closer}"


def _mapping_to_str(data: Mapping[Any, Any]) -> str:
    """Return a string representation of a mapping."""
    return _wrap_items(
        (f"{to_string(key)}:{to_string(value)}" for key, value in data.items()),
        opener="{",
        closer="}",
        sort=True,
    )


def _collection_to_str(
    data: Collection[Any],
    opener: str = "[",
    closer: str = "]",
    sort: bool = False,
) -> str:
    """Return a string representation of a collection."""
    items = (to_string(value) for value in data)
    return _wrap_items(items, opener, closer, sort=sort)


def to_string(data: Any) -> str:
    """Return a string representation of the input."""
    if isinstance(data, dict):
        return _mapping_to_str(data)
    if isinstance(data, list):
        return _collection_to_str(data)
    if isinstance(data, set):
        return _collection_to_str(data, "{", "}", sort=True)
    return repr(data)


def format_python(
    content: str,
    *,
    generator: str = DEFAULT_GENERATOR,
) -> str:
    """Format Python code with Black. Optionally prepend a generator comment."""
    if generator:
        content = f"""\"\"\"Automatically generated file.

To update, run python3 -m {generator}
\"\"\"

{content}
"""
    ruff = shutil.which("ruff")
    if not ruff:
        raise RuntimeError("ruff not found")
    return subprocess.check_output(
        [ruff, "format", "-"],
        input=content.strip(),
        encoding="utf-8",
    )


def format_python_namespace(
    content: dict[str, Any],
    *,
    annotations: dict[str, str] | None = None,
    generator: str = DEFAULT_GENERATOR,
) -> str:
    """Generate a nicely formatted "namespace" file.

    The keys of the `content` dict will be used as variable names.
    """

    def _get_annotation(key: str) -> str:
        annotation = (annotations or {}).get(key)
        return f": {annotation}" if annotation else ""

    code = "\n\n".join(
        f"{key}{_get_annotation(key)} = {to_string(value)}"
        for key, value in sorted(content.items())
    )
    if annotations:
        # If we had any annotations, add the __future__ import.
        code = f"from __future__ import annotations\n{code}"
    return format_python(code, generator=generator)
