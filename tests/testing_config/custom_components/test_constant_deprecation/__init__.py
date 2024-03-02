"""Test deprecated constants custom integration."""

from types import ModuleType
from typing import Any


def import_deprecated_constant(module: ModuleType, constant_name: str) -> Any:
    """Import and return deprecated constant."""
    return getattr(module, constant_name)
