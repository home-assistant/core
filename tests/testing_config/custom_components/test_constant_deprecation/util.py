"""util module for test_constant_deprecation tests."""

from enum import Enum
from types import ModuleType
from typing import Any


def import_and_test_deprecated_costant_enum(
    replacement: Enum, module: ModuleType, constant_prefix: str
) -> None:
    """Import and test deprecated constant."""
    assert getattr(module, constant_prefix + replacement.name) == replacement


def import_and_test_deprecated_costant(
    module: ModuleType, constant_name: str, replacement: Any
) -> None:
    """Import and test deprecated constant."""
    assert getattr(module, constant_name) == replacement
