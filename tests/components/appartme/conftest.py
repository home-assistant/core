"""Fixtures for Appartme integration tests."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.appartme.cloud_api import AppartmeCloudAPI


@pytest.fixture
def mock_appartme_api():
    """Fixture to mock the Appartme API."""
    mock_api = AsyncMock(spec=AppartmeCloudAPI)
    # Set up async mocks for methods
    mock_api.fetch_devices = AsyncMock()
    mock_api.fetch_device_details = AsyncMock()
    mock_api.get_device_properties = AsyncMock()
    mock_api.set_device_property_value = AsyncMock()
    return mock_api


@pytest.fixture(autouse=True)
def setup_logbook(hass):
    """Ensure the logbook component is set up for tests."""
    hass.config.components.add("logbook")
