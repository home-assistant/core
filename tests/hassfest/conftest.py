"""Fixtures for hassfest tests."""

from pathlib import Path
from unittest.mock import patch

import pytest

from script.hassfest.model import Config, Integration


@pytest.fixture
def config():
    """Fixture for hassfest Config."""
    return Config(
        root=Path(".").absolute(),
        specific_integrations=None,
        action="validate",
        requirements=True,
    )


@pytest.fixture
def mock_core_integration():
    """Mock Integration to be a core one."""
    with patch.object(Integration, "core", return_value=True):
        yield
