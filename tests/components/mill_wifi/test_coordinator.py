"""Tests for the Mill Data Coordinator."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mill_wifi.coordinator import MillDataCoordinator
from custom_components.mill_wifi.api import MillApiClient, MillApiError, AuthenticationError
from custom_components.mill_wifi.const import DOMAIN
from homeassistant.helpers.update_coordinator import UpdateFailed # Ensure this import is at the top
from custom_components.mill_wifi.device_capability import EDeviceType
# It's good practice to define some mock API responses or device data
# that can be reused across tests.
MOCK_DEVICES_DATA = [
    {"deviceId": "device_id_1", "name": "Heater 1", "type": EDeviceType.PANEL_HEATER_GEN3.value, "data": "some_data"},
    {"deviceId": "device_id_2", "name": "Socket 1", "type": EDeviceType.SOCKET_GEN3.value, "data": "other_data"},
]

MOCK_EMPTY_DEVICES_DATA = []

EXPECTED_MOCK_DEVICES_DICT = {
    device["deviceId"]: device for device in MOCK_DEVICES_DATA # MOCK_DEVICES_DATA is a list
} if MOCK_DEVICES_DATA else {}

EXPECTED_MOCK_EMPTY_DEVICES_DICT = {}

@pytest.fixture
def mock_api_client():
    """Fixture for a mock MillApiClient."""
    client = AsyncMock(spec=MillApiClient)
    client.username = "test_user"
    client.cloud_client_id = "test_client_id"
    client.cloud_client_secret = "test_client_secret"
    client.token = "test_token"
    client.token_expires_in = 3600
    client.token_updated_at = 0
    client.homes = AsyncMock(return_value={}) # Assuming homes might be used
    client.get_all_devices = AsyncMock(return_value=MOCK_DEVICES_DATA)
    return client

@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_api_client: MillApiClient):
    """Fixture for an initialized MillDataCoordinator."""
    # Mock the __init__ of MillApiClient to return our mock_api_client
    # when MillDataCoordinator tries to create it.
    # This is if MillDataCoordinator creates its own client.
    # If it's passed in, this might not be needed, or needs adjustment.
    with patch(
        "custom_components.mill_wifi.coordinator.MillApiClient",
        return_value=mock_api_client
    ):
        coord = MillDataCoordinator(hass, mock_api_client)
        # If MillDataCoordinator takes client directly, no need for the patch above,
        # just: coord = MillDataCoordinator(hass, mock_api_client)
    return coord


async def test_coordinator_initialization(hass: HomeAssistant, mock_api_client: MillApiClient):
    """Test coordinator initialization."""
    coordinator_instance = MillDataCoordinator(hass, mock_api_client)
    assert coordinator_instance.api == mock_api_client
    assert coordinator_instance.hass == hass

async def test_coordinator_successful_first_refresh(hass: HomeAssistant, coordinator: MillDataCoordinator, mock_api_client: MillApiClient):
    """Test the first successful data refresh."""
    # Ensure get_all_devices is called
    mock_api_client.get_all_devices.return_value = MOCK_DEVICES_DATA

    await coordinator.async_config_entry_first_refresh()

    mock_api_client.get_all_devices.assert_called_once()
    assert coordinator.data == EXPECTED_MOCK_DEVICES_DICT

async def test_coordinator_successful_update(hass: HomeAssistant, coordinator: MillDataCoordinator, mock_api_client: MillApiClient):
    """Test successful data update via _async_update_data."""
    mock_api_client.get_all_devices.return_value = MOCK_DEVICES_DATA
    data = await coordinator._async_update_data()
    assert data == EXPECTED_MOCK_DEVICES_DICT
    mock_api_client.get_all_devices.assert_called_once()

async def test_coordinator_update_with_no_devices(hass: HomeAssistant, coordinator: MillDataCoordinator, mock_api_client: MillApiClient):
    """Test data update when API returns no devices."""
    mock_api_client.get_all_devices.return_value = MOCK_EMPTY_DEVICES_DATA
    data = await coordinator._async_update_data()
    assert data == EXPECTED_MOCK_EMPTY_DEVICES_DICT # Which is {}

async def test_coordinator_update_raises_authentication_error(hass: HomeAssistant, coordinator: MillDataCoordinator, mock_api_client: MillApiClient):
    """Test data update when API raises AuthenticationError."""
    mock_api_client.get_all_devices.side_effect = AuthenticationError("Auth failed")

    with pytest.raises(UpdateFailed, match="Error fetching devices: Auth failed"): # Or UpdateFailed if it's caught and re-raised
        await coordinator._async_update_data()

async def test_coordinator_update_raises_mill_api_error(hass: HomeAssistant, coordinator: MillDataCoordinator, mock_api_client: MillApiClient):
    """Test data update when API raises MillApiError."""
    mock_api_client.get_all_devices.side_effect = MillApiError("API communication failed")
    # In Home Assistant, coordinators usually raise UpdateFailed
    from homeassistant.helpers.update_coordinator import UpdateFailed
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

async def test_coordinator_first_refresh_raises_config_entry_not_ready_on_auth_error(
    hass: HomeAssistant, mock_api_client: MillApiClient
):
    """Test first refresh raises ConfigEntryNotReady on AuthenticationError."""
    mock_api_client.get_all_devices.side_effect = AuthenticationError("Auth failed during first refresh")
    # Re-create coordinator for this specific test case if needed,
    # or ensure the fixture mock_api_client's side_effect is set correctly before coordinator init.
    coordinator_instance = MillDataCoordinator(hass, mock_api_client)

    with pytest.raises(ConfigEntryNotReady) as excinfo:
        await coordinator_instance.async_config_entry_first_refresh()
    assert "Auth failed during first refresh" in str(excinfo.value)


async def test_coordinator_first_refresh_raises_config_entry_not_ready_on_api_error(
    hass: HomeAssistant, mock_api_client: MillApiClient
):
    """Test first refresh raises ConfigEntryNotReady on MillApiError."""
    mock_api_client.get_all_devices.side_effect = MillApiError("API error during first refresh")
    coordinator_instance = MillDataCoordinator(hass, mock_api_client)

    with pytest.raises(ConfigEntryNotReady) as excinfo:
        await coordinator_instance.async_config_entry_first_refresh()
    assert "API error during first refresh" in str(excinfo.value)
