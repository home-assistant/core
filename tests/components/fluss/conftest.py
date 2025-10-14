"""Shared test fixtures for Fluss+ integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fluss_api import FlussApiClient
import pytest

from homeassistant.components.fluss.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Fluss Integration",
        data={CONF_API_KEY: "test_api_key"},
        unique_id="test_api_key",
    )


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Mock Fluss API client with single device."""
    with (
        patch(
            "homeassistant.components.fluss.coordinator.FlussApiClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.fluss.config_flow.FlussApiClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_get_devices.return_value = {
            "devices": [{"deviceId": "1", "deviceName": "Test Device"}]
        }
        client.async_trigger_device.return_value = None
        yield client


@pytest.fixture
def mock_api_client_multiple_devices() -> AsyncMock:
    """Mock Fluss API client with multiple devices."""
    with patch(
        "homeassistant.components.fluss.coordinator.FlussApiClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.async_get_devices.return_value = {
            "devices": [
                {"deviceId": "2a303030sdj1", "deviceName": "Device 1"},
                {"deviceId": "ape93k9302j2", "deviceName": "Device 2"},
            ]
        }
        client.async_trigger_device.return_value = None
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api_client: AsyncMock
) -> MockConfigEntry:
    """Set up the Fluss integration for testing."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
