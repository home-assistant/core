"""Fixtures for the shared hassfest package."""

from pathlib import Path

from hassfest.model import Config
import pytest


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Return configuration for a temporary integration tree."""
    return Config(
        root=tmp_path,
        specific_integrations=None,
        action="validate",
        requirements=False,
    )
