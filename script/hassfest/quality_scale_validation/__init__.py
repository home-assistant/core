"""Integration quality scale rules."""

from typing import Protocol

from script.hassfest.model import Config, Integration


class RuleValidationProtocol(Protocol):
    """Protocol for rule validation."""

    def validate(self, config: Config, integration: Integration) -> list[str] | None:
        """Validate a quality scale rule.

        Returns error (if any).
        """
