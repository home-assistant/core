"""Helpers for loading Novy cooker-hood RF commands."""

from __future__ import annotations

from typing import Final

from rf_protocols import CodeCollection, get_codes

COMMAND_LIGHT: Final = "light"
COMMAND_PLUS: Final = "plus"
COMMAND_MINUS: Final = "minus"


def get_codes_for_code(code: int) -> CodeCollection:
    """Return the bundled `rf-protocols` collection for a Novy cooker-hood code."""
    return get_codes(f"novy/cooker_hood/code_{code}")
