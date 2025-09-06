"""Tests for the Mill WiFi number platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.mill_wifi.api import MillApiClient
from custom_components.mill_wifi.const import DOMAIN
from custom_components.mill_wifi.coordinator import MillDataCoordinator
from custom_components.mill_wifi.device_capability import EDeviceCapability, EDeviceType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

# --- MOCK DATA ---
MOCK_HEATER_ID = "heater_789"
MOCK_HEATER_NAME = "Bedroom Heater"
MOCK_DEVICE_DATA_HEATER_NUMBER = {
    MOCK_HEATER_ID: {
        "deviceId": MOCK_HEATER_ID,
        "customName": MOCK_HEATER_NAME,
        "deviceType": {"childType": {"name": EDeviceType.PANEL_HEATER_GEN3.value}},
        "isEnabled": True,
        "isConnected": True,
        "deviceSettings": {"reported": {"temperature_normal": 20.0}},
        "capabilities": [
            EDeviceCapability.TARGET_TEMPERATURE.value
        ],
    }
}

MOCK_SOCKET_ID = "socket_123"
MOCK_SOCKET_NAME = "Office Socket"
MOCK_DEVICE_DATA_SOCKET_WATTAGE = {
    MOCK_SOCKET_ID: {
        "deviceId": MOCK_SOCKET_ID,
        "customName": MOCK_SOCKET_NAME,
        "deviceType": {"childType": {"name": EDeviceType.SOCKET_GEN3.value}},
        "isEnabled": True,
        "isConnected": True,
        "deviceSettings": {"reported": {"limited_heating_power": 1000}},
        "capabilities": [EDeviceCapability.ADJUST_WATTAGE.value],
    }
}


# --- PYTEST FIXTURES ---
@pytest.fixture
def mock_mill_api_client_fixture():
    """Fixture for a mocked MillApiClient."""
    client = MagicMock(spec=MillApiClient)
    client.login = AsyncMock(return_value=None)
    client.async_setup = AsyncMock(return_value=None)
    client.get_all_devices = AsyncMock(
        return_value=[MOCK_DEVICE_DATA_HEATER_NUMBER[MOCK_HEATER_ID]]
    )
    client.set_number_capability = AsyncMock(return_value=None)
    return client


@pytest.fixture
async def setup_integration_fixture(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Help fixture to set up the integration for number tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test@example.com", "password": "password"},
        entry_id="test_number_entry_fixture",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        mock_mill_api_client_fixture.get_all_devices.return_value = [
            MOCK_DEVICE_DATA_HEATER_NUMBER[MOCK_HEATER_ID]
        ]

        assert await hass.config_entries.async_setup(entry.entry_id) is True, (
            "Failed to set up config entry"
        )
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    if not coordinator.data:
        coordinator.data = {
            MOCK_HEATER_ID: MOCK_DEVICE_DATA_HEATER_NUMBER[MOCK_HEATER_ID]
        }
    await hass.async_block_till_done()
    return entry


# --- TEST CASES ---
async def test_no_numbers_if_no_devices(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Test that no number entities are created if there are no devices or no data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test", "password": "pwd"},
        entry_id="no_devices_entry",
    )
    entry.add_to_hass(hass)

    mock_mill_api_client_fixture.get_all_devices.return_value = []  # No devices

    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    assert len(hass.states.async_all(NUMBER_DOMAIN)) == 0


async def test_target_temperature_number_creation(
    hass: HomeAssistant, setup_integration_fixture: MockConfigEntry
):
    """Test creation of a target temperature number entity."""

    entity_id = f"{NUMBER_DOMAIN}.{MOCK_HEATER_NAME.lower().replace(' ', '_')}_target_temperature"
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == "20.0"
    assert state.attributes.get("min") == 5.0
    assert state.attributes.get("max") == 35.0
    assert state.attributes.get("step") == 0.5
    assert state.attributes.get("mode") == "slider"


async def test_set_target_temperature_number_value(
    hass: HomeAssistant,
    setup_integration_fixture: MockConfigEntry,
    mock_mill_api_client_fixture: MagicMock,
):
    """Test setting the value for a target temperature number entity."""

    entity_id = f"{NUMBER_DOMAIN}.{MOCK_HEATER_NAME.lower().replace(' ', '_')}_target_temperature"
    target_value = 23.5

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: target_value},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_mill_api_client_fixture.set_number_capability.assert_called_once_with(
        MOCK_HEATER_ID,
        EDeviceCapability.TARGET_TEMPERATURE.value,
        target_value,
        MOCK_DEVICE_DATA_HEATER_NUMBER[MOCK_HEATER_ID],
    )


async def test_adjust_wattage_number_creation(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Test creation of an adjust wattage number entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test", "password": "pwd"},
        entry_id="wattage_entry",
    )
    entry.add_to_hass(hass)

    mock_mill_api_client_fixture.get_all_devices.return_value = [
        MOCK_DEVICE_DATA_SOCKET_WATTAGE[MOCK_SOCKET_ID]
    ]

    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.data = {MOCK_SOCKET_ID: MOCK_DEVICE_DATA_SOCKET_WATTAGE[MOCK_SOCKET_ID]}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id = f"{NUMBER_DOMAIN}.{MOCK_SOCKET_NAME.lower().replace(' ', '_')}_limited_heating_power"
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == "1000.0"
    assert state.attributes.get("min") == 0
    assert state.attributes.get("max") == 2500
    assert state.attributes.get("step") == 100


async def test_set_adjust_wattage_number_value(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Test setting the value for an adjust wattage number entity."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test", "password": "pwd"},
        entry_id="set_wattage_entry",
    )
    entry.add_to_hass(hass)

    mock_mill_api_client_fixture.get_all_devices.return_value = [
        MOCK_DEVICE_DATA_SOCKET_WATTAGE[MOCK_SOCKET_ID]
    ]

    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.data = {MOCK_SOCKET_ID: MOCK_DEVICE_DATA_SOCKET_WATTAGE[MOCK_SOCKET_ID]}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id = f"{NUMBER_DOMAIN}.{MOCK_SOCKET_NAME.lower().replace(' ', '_')}_limited_heating_power"
    target_value = 1200.0

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: target_value},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_mill_api_client_fixture.set_number_capability.assert_called_once_with(
        MOCK_SOCKET_ID,
        EDeviceCapability.ADJUST_WATTAGE.value,
        target_value,
        MOCK_DEVICE_DATA_SOCKET_WATTAGE[MOCK_SOCKET_ID],
    )
