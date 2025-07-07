"""Fixtures for the TuneBlade Remote integration tests."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_tuneblade_api():
    """Fixture to mock the TuneBlade API client."""
    with patch(
        "homeassistant.components.tuneblade_remote.config_flow.TuneBladeApiClient"
    ) as mock_client:
        instance = mock_client.return_value
        instance.async_get_data = AsyncMock(return_value=[{"id": "abc"}])
        yield instance
