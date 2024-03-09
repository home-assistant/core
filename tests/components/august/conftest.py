"""August tests conftest."""

from unittest.mock import patch

import pytest


@pytest.fixture(name="mock_discovery", autouse=True)
def mock_discovery_fixture():
    """Mock discovery to avoid loading the whole bluetooth stack."""
    with patch(
        "homeassistant.components.august.discovery_flow.async_create_flow"
    ) as mock_discovery:
        yield mock_discovery
