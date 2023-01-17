"""Helpers for Asus Router component."""

from __future__ import annotations

import re
from typing import Any


def flatten_dict(obj: Any, keystring: str = "", delimiter: str = "_"):
    """Flatten dictionary."""

    if isinstance(obj, dict):
        keystring = keystring + delimiter if keystring else keystring
        for key in obj:
            yield from flatten_dict(obj[key], keystring + str(key))
    else:
        yield keystring, obj


def as_dict(pyobj):
    """Return generator object as dictionary."""

    return dict(pyobj)


def list_from_dict(raw: dict[str, Any]) -> list[str]:
    """Return dictionary keys as list."""

    return list(raw.keys())


def to_unique_id(raw: str):
    """Convert string to unique_id."""

    string = (
        re.sub(r"(?<=[a-z0-9:_])(?=[A-Z])|[^a-zA-Z0-9:_]", " ", raw)
        .strip()
        .replace(" ", "_")
    )
    result = "".join(string.lower())
    while "__" in result:
        result = result.replace("__", "_")

    return result
