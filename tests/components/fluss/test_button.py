"""Test Script for Fluss Button."""

from unittest.mock import AsyncMock, Mock, patch

from fluss_api import FlussApiClient
import pytest

from homeassistant.components.fluss.button import FlussButton, async_setup_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


@pytest.fixture
def mock_hass():
    """Mock Home Assistant Environment."""
    hass = Mock(spec=HomeAssistant)
    hass.config_entries = Mock()
    return hass


@pytest.fixture
def mock_entry():
    """Mock API Entry."""
    entry = Mock(spec=ConfigEntry)
    entry.data = {"api_key": "test_api_key"}
    entry.runtime_data = {}
    return entry


@pytest.fixture
def mock_api_client():
    """Mock API Client Session."""
    api_client = Mock(spec=FlussApiClient)
    api_client.async_get_devices = AsyncMock(
        return_value={"devices": [{"deviceId": "1", "deviceName": "Test Device"}]}
    )
    return api_client


@pytest.mark.asyncio
async def test_async_setup_entry(mock_hass, mock_entry, mock_api_client) -> None:
    """Test successful setup of the button."""
    mock_entry.runtime_data = {"api": mock_api_client}
    async_add_entities = Mock(spec=AddEntitiesCallback)

    await async_setup_entry(mock_hass, mock_entry, async_add_entities)

    async_add_entities.assert_called_once()


@pytest.mark.asyncio
async def test_fluss_button() -> None:
    """Test Scenario of Fluss Button."""
    mock_api = Mock(spec=FlussApiClient)
    device = {"deviceId": "1", "deviceName": "Test Device"}
    button = FlussButton(mock_api, device)

    assert button.name == "Test Device"

    with patch.object(mock_api, "async_trigger_device", new=AsyncMock()):
        await button.async_press()
        mock_api.async_trigger_device.assert_called_once_with("1")
