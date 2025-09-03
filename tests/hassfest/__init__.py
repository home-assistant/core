"""Tests for hassfest."""

from pathlib import Path

from script.hassfest.model import Config, Integration


def get_integration(domain: str, config: Config):
    """Fixture for hassfest integration model."""
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
