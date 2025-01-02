"""Util to gather system info."""

from __future__ import annotations

from functools import cache
import os


@cache
def is_official_image() -> bool:
    """Return True if Home Assistant is running in an official container."""
    return os.path.isfile("/OFFICIAL_IMAGE")
