"""Fixtures for UniFi methods."""
import pytest

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def mock_discovery():
    """No real network traffic allowed."""
    with patch(
        "homeassistant.components.unifi.config_flow.async_discover_unifi",
        return_value=None,
    ) as mock:
        yield mock
