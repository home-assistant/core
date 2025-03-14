"""Test Script for Fluss Button."""

from unittest.mock import AsyncMock, Mock, patch

from fluss_api import FlussApiClient
import pytest

from homeassistant.components.fluss.button import (
    FlussButton,
    async_setup_entry,
    validate_device,
)
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


@pytest.mark.asyncio
async def test_fluss_button_initialization_success() -> None:
    """Test successful initialization of FlussButton."""
    mock_api = Mock(spec=FlussApiClient)
    device = {"deviceId": "123", "deviceName": "Test Device"}

    button = FlussButton(api=mock_api, device=device)

    assert button.name == "Test Device"
    assert button._attr_unique_id == "fluss_123"


@pytest.mark.asyncio
async def test_fluss_button_initialization_missing_device_id() -> None:
    """Test initialization of FlussButton with missing deviceId raises ValueError."""
    mock_api = Mock(spec=FlussApiClient)
    device = {"deviceName": "Test Device"}  # Missing 'deviceId'

    with pytest.raises(
        ValueError, match="Device missing required 'deviceId' attribute."
    ):
        FlussButton(api=mock_api, device=device)


@pytest.mark.asyncio
async def test_fluss_button_async_press_success() -> None:
    """Test the async_press method of FlussButton."""
    mock_api = Mock(spec=FlussApiClient)
    device = {"deviceId": "123"}

    button = FlussButton(api=mock_api, device=device)

    # Mock the async_trigger_device method to ensure it gets called
    mock_api.async_trigger_device = AsyncMock()

    await button.async_press()

    # Assert that the method was called with the correct deviceId
    mock_api.async_trigger_device.assert_called_once_with("123")


def test_validate_device_success() -> None:
    """Test validate_device with valid device data."""
    device = {"deviceId": "123", "deviceName": "Test Device"}
    assert validate_device(device) is True  # Should return True


def test_validate_device_failure_not_a_dict() -> None:
    """Test validate_device with a non-dictionary device."""
    device = ["deviceId", "123"]  # Invalid data type
    with pytest.raises(ValueError, match="Invalid device data: 'deviceId' is required"):
        validate_device(device)


def test_validate_device_failure_missing_device_id() -> None:
    """Test validate_device with missing deviceId."""
    device = {"deviceName": "Test Device"}  # Missing 'deviceId'
    with pytest.raises(ValueError, match="Invalid device data: 'deviceId' is required"):
        validate_device(device)
