"""Integration quality scale rules."""

from script.hassfest.model import Integration


class QualityScaleCheck:
    """Quality scale check interface for error reporting."""

    def __init__(self, integration: Integration) -> None:
        """Initialize a quality scale check."""
        self.integration = integration
        self.errors: list[str] = []

    def add_error(self, rule_name: str, error: str) -> None:
        """Add an error."""
        self.integration.add_error(
            "quality_scale",
            f"[{rule_name}] {error}",
        )
