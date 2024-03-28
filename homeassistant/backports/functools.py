"""Functools backports from standard lib.

This file contained the backport of the cached_property implementation of Python 3.12.

Since we have dropped support for Python 3.11, we can remove this backport.
This file is kept for now to avoid breaking custom components that might
import it.
"""

from __future__ import annotations

from functools import cached_property

__all__ = [
    "cached_property",
]
