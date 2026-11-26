"""Helpers for the Evohome integration."""

import re


def as_snake_case(mode: str) -> str:
    """Convert a CamelCase string to the snake_case used by the library."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", mode).lower()


def as_camel_case(mode: str) -> str:
    """Convert a snake_case string used by the library to CamelCase."""
    return "".join(word.capitalize() for word in mode.split("_"))
