"""Helpers for entity translation keys."""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def param_to_translation_key(param: str) -> str:
    """Convert a KWB parameter name to a stable HA translation key."""
    normalized = _NON_ALNUM.sub("_", param.lower()).strip("_")
    return f"reg_{normalized}"

