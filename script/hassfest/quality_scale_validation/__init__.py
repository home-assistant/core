"""Integration quality scale rules."""

from typing import Protocol

from script.hassfest.model import Integration


class RuleValidationProtocol(Protocol):
    """Protocol for rule validation."""

    def validate(self, integration: Integration) -> list[str] | None:
        """Validate a quality scale rule.

        Returns error (if any).
        """
