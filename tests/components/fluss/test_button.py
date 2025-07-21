"""Test Script for Fluss Button."""

from unittest.mock import AsyncMock, Mock, patch

from fluss_api import FlussApiClient
import pytest

from homeassistant.components.fluss import CONF_API_KEY
from homeassistant.components.fluss.button import FlussButton, async_setup_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import FlussDataUpdateCoordinator


@pytest.fixture
def mock_hass() -> HomeAssistant:
    """Mock Home Assistant Environment."""
    hass = Mock(spec=HomeAssistant)
    hass.config_entries = Mock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    return hass


@pytest.fixture
def mock_entry() -> ConfigEntry:
    """Mock API Entry."""
    entry = Mock(spec=ConfigEntry)
    entry.data = {CONF_API_KEY: "test_api_key"}
    entry.runtime_data = None  # Will be set by integration setup
    return entry


@pytest.fixture
def mock_api_client() -> FlussApiClient:
    """Mock API Client Session."""
    api_client = Mock(spec=FlussApiClient)
    api_client.async_get_devices = AsyncMock(
        return_value={"devices": [{"deviceId": "1", "deviceName": "Test Device"}]}
    )
    return api_client


@pytest.fixture
def mock_fluss_api_client(mock_api_client: FlussApiClient) -> FlussApiClient:
    """Mock the FlussApiClient class."""
    with patch("fluss_api.main.FlussApiClient", return_value=mock_api_client):
        yield mock_api_client


@pytest.fixture
def mock_coordinator(mock_hass: HomeAssistant, mock_api_client: FlussApiClient) -> FlussDataUpdateCoordinator:
    """Mock the FlussDataUpdateCoordinator."""
    coordinator = Mock(spec=FlussDataUpdateCoordinator)
    coordinator.hass = mock_hass
    coordinator.api = mock_api_client
    coordinator.data = {"1": {"deviceId": "1", "deviceName": "Test Device"}}
    coordinator.async_config_entry_first_refresh = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry(
    mock_hass: HomeAssistant, mock_entry: ConfigEntry, mock_coordinator: FlussDataUpdateCoordinator
) -> None:
    """Test successful setup of the button."""
    added_entities = []

    async def mock_add_entities(entities, update_before_add=False):
        added_entities.extend(entities)

    with patch(
        "homeassistant.components.fluss.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)
        mock_setup.assert_awaited_once_with(mock_hass, mock_entry)

    # Verify that async_get_devices was called via coordinator
    mock_coordinator.api.async_get_devices.assert_awaited_once()

    # Verify that FlussButton instances were created correctly
    assert len(added_entities) == 1
    added_button = added_entities[0]
    assert isinstance(added_button, FlussButton)
    assert added_button.api == mock_coordinator.api
    assert added_button.device == {"deviceId": "1", "deviceName": "Test Device"}
    assert added_button.name == "Test Device"
    assert added_button.unique_id == "fluss_1"
    # Verify DeviceInfo
    assert added_button.device_info == DeviceInfo(
        identifiers={("fluss", "1")},
        name="Test Device",
        manufacturer="Fluss",
        model="Fluss Device",
    )


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
    mock_hass: HomeAssistant, mock_entry: ConfigEntry, mock_coordinator: FlussDataUpdateCoordinator
) -> None:
    """Test setup when no devices are returned."""
    mock_coordinator.data = {}
    mock_coordinator.api.async_get_devices = AsyncMock(return_value={"devices": []})
    mock_add_entities = AsyncMock(spec=AddEntitiesCallback)

    with patch(
        "homeassistant.components.fluss.async_setup_entry",
        return_value=True,
    ):
        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

    # No buttons should be added
    mock_add_entities.assert_called_once_with([])


@pytest.mark.asyncio
async def test_async_setup_entry_exception(
    mock_hass: HomeAssistant, mock_entry: ConfigEntry, mock_coordinator: FlussDataUpdateCoordinator
) -> None:
    """Test setup entry when async_get_devices raises an exception."""
    mock_coordinator.api.async_get_devices = AsyncMock(
        side_effect=Exception("Unexpected error")
    )
    mock_add_entities = AsyncMock(spec=AddEntitiesCallback)

    with patch(
        "homeassistant.components.fluss.async_setup_entry",
        return_value=True,
    ):
        await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

    # Verify no entities were added due to exception
    mock_add_entities.assert_called_once_with([])


@pytest.mark.asyncio
async def test_fluss_button_initialization_success() -> None:
    """Test successful initialization of FlussButton."""
    mock_api = Mock(spec=FlussApiClient)
    device = {"deviceId": "123", "deviceName": "Test Device"}

    button = FlussButton(api=mock_api, device=device)

    assert button.name == "Test Device"
    assert button._attr_unique_id == "fluss_123"
    assert button.device_info == DeviceInfo(
        identifiers={("fluss", "123")},
        name="Test Device",
        manufacturer="Fluss",
        model="Fluss Device",
    )


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