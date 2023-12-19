"""util module for test_constant_deprecation tests."""

from enum import Enum
from types import ModuleType


def import_and_test_deprecated_costant(
    replacement: Enum, module: ModuleType, constant_prefix: str
) -> None:
    """Import and test deprecated constant."""
    assert getattr(module, constant_prefix + replacement.name) == replacement
