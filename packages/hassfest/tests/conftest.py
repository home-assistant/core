"""Fixtures for the shared hassfest package."""

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

from hassfest.model import Config, Integration
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


@pytest.fixture
def mock_core_integration() -> Generator[None]:
    """Mock Integration to be a core one."""
    with patch.object(Integration, "core", return_value=True):
        yield
