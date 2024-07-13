"""Functools backports from standard lib.

This file contained the backport of the cached_property implementation of Python 3.12.

Since we have dropped support for Python 3.11, we can remove this backport.
This file is kept for now to avoid breaking custom components that might
import it.
"""

from __future__ import annotations

from functools import cached_property as _cached_property, partial

from homeassistant.helpers.deprecation import (
    DeprecatedAlias,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

# cached_property deprecated as of 2024.5 use functools.cached_property instead.
_DEPRECATED_cached_property = DeprecatedAlias(
    _cached_property, "functools.cached_property", "2025.5"
)

__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
