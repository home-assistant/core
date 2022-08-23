"""fnmatch utility functions."""
from __future__ import annotations

from fnmatch import translate
from functools import lru_cache
from os.path import normcase
import re


@lru_cache(maxsize=4096, typed=True)
def compile_fnmatch(pattern: str) -> re.Pattern:
    """Compile a fnmatch pattern."""
    return re.compile(translate(normcase(pattern)))


def memorized_fnmatch(name: str, pattern: str) -> bool:
    """Memorized version of fnmatch that has a larger lru_cache.

    The default version of fnmatch only has a lru_cache of 256 entries.
    With many devices we quickly reach that limit and end up compiling
    the same pattern over and over again.
    """
    return bool(compile_fnmatch(pattern).match(normcase(name)))
