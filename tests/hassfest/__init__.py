"""Tests for hassfest."""

from pathlib import Path

from script.hassfest.model import Config, Integration


def get_integration(domain: str, config: Config):
    """Helper function for creating hassfest integration model instances."""
    return Integration(
        Path(domain),
        _config=config,
        _manifest={
            "domain": domain,
            "name": domain,
            "documentation": "https://example.com",
            "codeowners": ["@awesome"],
        },
    )
