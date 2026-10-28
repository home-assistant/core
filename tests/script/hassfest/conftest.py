"""Fixtures for hassfest tests."""

from pathlib import Path
from unittest.mock import patch

from hassfest.model import Config, Integration
import pytest

import homeassistant


@pytest.fixture
def config() -> Config:
    """Fixture for hassfest Config."""
    return Config(
        root=Path(homeassistant.__file__).parent.parent,
        specific_integrations=None,
        action="validate",
        requirements=True,
    )


@pytest.fixture
def mock_core_integration():
    """Mock Integration to be a core one."""
    with patch.object(Integration, "core", return_value=True):
        yield
