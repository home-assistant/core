"""Fixtures for hassfest tests."""

from pathlib import Path

from hassfest.model import Config
import pytest


@pytest.fixture
def config() -> Config:
    """Fixture for hassfest Config."""
    return Config(
        root=Path(".").absolute(),
        specific_integrations=None,
        action="validate",
        requirements=True,
    )
