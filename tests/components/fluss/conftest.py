"""Shared test fixtures for Fluss+ integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
        unique_id="test_unique_id",
    )


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Mock Fluss API client."""
    client = MagicMock(spec=FlussApiClient)
    client.async_get_devices = MagicMock(
        return_value={"devices": [{"deviceId": "1", "deviceName": "Test Device"}]}
    )
    client.async_trigger_device = MagicMock()
    return client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api_client: MagicMock
) -> MockConfigEntry:
    """Set up the Fluss integration for testing."""
    with patch("fluss_api.FlussApiClient", return_value=mock_api_client):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    return mock_config_entry
