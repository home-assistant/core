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
    entry.runtime_data = None  # Will be set in tests
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
    mock_entry.runtime_data = mock_api_client  # Assign directly, not as a dict
    mock_add_entities = AsyncMock(spec=AddEntitiesCallback)
    mock_api_client.async_get_devices.return_value = {
        "devices": [{"deviceId": "1", "deviceName": "Test Device"}]
    }
    # Patch to return the mock API client
    with patch(
        "fluss_api.main.FlussApiClient",
        return_value=mock_api_client,
    ):
        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

    # Verify that async_get_devices was called
    mock_api_client.async_get_devices.assert_awaited_once()

    # Verify that FlussButton instances were created correctly
    mock_add_entities.assert_called_once()
    added_entities = mock_add_entities.call_args[0][0]
    assert len(added_entities) == 1
    added_button = added_entities[0]
    assert isinstance(added_button, FlussButton)
    assert added_button.api == mock_api_client
    assert added_button.device == {"deviceId": "1", "deviceName": "Test Device"}
    assert added_button.name == "Test Device"
    assert added_button.unique_id == "fluss_1"


@pytest.mark.asyncio
async def test_fluss_button() -> None:
    """Test Scenario of Fluss Button."""
    mock_api = Mock(spec=FlussApiClient)
    device = {"deviceId": "1", "deviceName": "Test Device"}
    button = FlussButton(mock_api, device)

    assert button.name == "Test Device"

    with patch.object(
        mock_api, "async_trigger_device", new=AsyncMock()
    ) as mock_trigger:
        await button.async_press()
        mock_trigger.assert_called_once_with("1")


@pytest.mark.asyncio
async def test_async_setup_entry_no_devices(
    mock_hass, mock_entry, mock_api_client
) -> None:
    """Test setup when no devices are returned."""
    mock_entry.runtime_data = mock_api_client
    mock_api_client.async_get_devices = AsyncMock(return_value={"devices": []})
    async_add_entities = AsyncMock(spec=AddEntitiesCallback)

    await async_setup_entry(mock_hass, mock_entry, async_add_entities)

    # No buttons should be added
    async_add_entities.assert_called_once_with([])


@pytest.mark.asyncio
async def test_async_setup_entry_exception(
    mock_hass, mock_entry, mock_api_client
) -> None:
    """Test setup entry when async_get_devices raises an exception."""
    mock_entry.runtime_data = mock_api_client
    mock_api_client.async_get_devices = AsyncMock(
        side_effect=Exception("Unexpected error")
    )
    async_add_entities = AsyncMock(spec=AddEntitiesCallback)

    with pytest.raises(Exception):  # noqa: B017
        await async_setup_entry(mock_hass, mock_entry, async_add_entities)
