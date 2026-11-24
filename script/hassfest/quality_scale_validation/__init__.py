"""Integration quality scale rules."""

import ast
from typing import Protocol

from hassfest.model import Config, Integration


def has_base_class(module: ast.Module, names: set[str]) -> bool:
    """Test if a class in the module directly subclasses one of the named classes."""
    return any(
        (isinstance(base, ast.Name) and base.id in names)
        or (isinstance(base, ast.Attribute) and base.attr in names)
        for item in ast.walk(module)
        if isinstance(item, ast.ClassDef)
        for base in item.bases
    )


class RuleValidationProtocol(Protocol):
    """Protocol for rule validation."""

    def validate(
        self, config: Config, integration: Integration, *, rules_done: set[str]
    ) -> list[str] | None:
        """Validate a quality scale rule.

        Returns error (if any).
        """
