"""Enum backports from standard lib.

This file contained the backport of the StrEnum of Python 3.11.

Since we have dropped support for Python 3.10, we can remove this backport.
This file is kept for now to avoid breaking custom components that might
import it.
"""

from __future__ import annotations

from enum import StrEnum as _StrEnum
from functools import partial

from homeassistant.helpers.deprecation import (
    DeprecatedAlias,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

# StrEnum deprecated as of 2024.5 use enum.StrEnum instead.
_DEPRECATED_StrEnum = DeprecatedAlias(_StrEnum, "enum.StrEnum", "2025.5")

__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
