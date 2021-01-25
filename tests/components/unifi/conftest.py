"""Fixtures for UniFi methods."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_discovery():
    """No real network traffic allowed."""
    with patch(
        "homeassistant.components.unifi.config_flow.async_discover_unifi",
        return_value=None,
    ) as mock:
        yield mock
