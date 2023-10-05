"""Enum backports from standard lib.

This file contained the backport of the StrEnum of Python 3.11.

Since we have dropped support for Python 3.10, we can remove this backport.
This file is kept for now to avoid breaking custom components that might
import it.
"""
from __future__ import annotations

from enum import StrEnum

__all__ = [
    "StrEnum",
]
