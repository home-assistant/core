"""Tests for the Mill Number platform."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    ATTR_DEVICE_CLASS,
    UnitOfTemperature,
    UnitOfPower, # If you have power limit numbers
)
from homeassistant.components.number import (
    ATTR_MIN,
    ATTR_MAX,
    ATTR_STEP,
    ATTR_MODE,
    ATTR_VALUE,
    NumberDeviceClass,
    NumberMode,
    SERVICE_SET_VALUE,
)
from homeassistant.setup import async_setup_component
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.entity import EntityCategory
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mill_wifi.const import DOMAIN
from custom_components.mill_wifi.coordinator import MillDataCoordinator
from custom_components.mill_wifi.api import MillApiClient
from custom_components.mill_wifi.number import NUMBER_TYPES # Ensure this is defined
from custom_components.mill_wifi.device_capability import EDeviceCapability, EDeviceType

# Sample device data - expand to cover number scenarios
MOCK_DEVICE_ID_HEATER_FOR_NUMBER = "heater_device_789"
MOCK_DEVICE_DATA_HEATER_NUMBER = {
    MOCK_DEVICE_ID_HEATER_FOR_NUMBER: {
        "deviceId": MOCK_DEVICE_ID_HEATER_FOR_NUMBER,
        "deviceName": "Office Heater",
        "houseId": "house_1",
        "type": EDeviceType.PANEL_HEATER_GEN3.value,
        "capabilities": [
            EDeviceCapability.TARGET_TEMPERATURE.value, # Assuming this can be a number
            # Add other capabilities that might result in number entities
        ],
        "deviceSettings": {"temperatureNormal": 20}, # Example for target temp
        "lastMetrics": {"temperature": 19.5},
        "reported": {"targetTemperature": 20.0, "powerState": "on"},
        # Define min/max/step if available from API or constants
        "temperatureLimits": {"min": 5, "max": 35, "step": 1}, # Hypothetical structure
    }
}

MOCK_DEVICE_ID_SOCKET_FOR_NUMBER = "socket_device_101"
MOCK_DEVICE_DATA_SOCKET_NUMBER = {
    MOCK_DEVICE_ID_SOCKET_FOR_NUMBER: {
        "deviceId": MOCK_DEVICE_ID_SOCKET_FOR_NUMBER,
        "deviceName": "Smart Socket",
        "houseId": "house_1",
        "type": EDeviceType.SOCKET_GEN3.value, # Or other relevant type
        "capabilities": [
            EDeviceCapability.ADJUST_WATTAGE.value, # Assuming this capability
        ],
        "deviceSettings": {"maxPowerConsumption": 1000}, # Example value
        "reported": {"maxPowerConsumption": 1000},
        # Define min/max/step if available
        "maxPowerLimits": {"min": 100, "max": 2000, "step": 50}, # Hypothetical
    }
}


@pytest.fixture # In test_number.py
def mock_api_client():
    client = AsyncMock(spec=MillApiClient)
    client.connect = AsyncMock(return_value=True)
    client.get_all_devices = AsyncMock(return_value=[]) # Default or specific mock data
    client.set_number_control = AsyncMock(return_value=True)
    return client

@pytest.fixture
async def mock_coordinator(hass: HomeAssistant, mock_api_client: MillApiClient):
    """Fixture for a mock MillDataCoordinator."""
    coordinator = MillDataCoordinator(hass, mock_api_client)
    coordinator.data = {}
    return coordinator

@pytest.fixture
def mock_config_entry():
    """Fixture for a mock ConfigEntry."""
    return MockConfigEntry(domain=DOMAIN, data={"username": "test_user", "password": "test_password"})


async def setup_mill_component_number(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    coordinator: MillDataCoordinator
):
    """Set up the Mill component for testing numbers."""
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with patch("custom_components.mill_wifi.PLATFORMS", ["number"]):
         await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_no_numbers_if_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MillDataCoordinator
):
    """Test that no number entities are created if there are no devices or no data."""
    mock_coordinator.data = {}
    await setup_mill_component_number(hass, mock_config_entry, mock_coordinator)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    assert len(entity_registry.entities) == 0


async def test_target_temperature_number_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MillDataCoordinator,
    mock_api_client: MillApiClient
):
    """Test creation of a target temperature number entity."""
    mock_api_client.get_all_devices.return_value = MOCK_DEVICE_DATA_HEATER_NUMBER
    mock_coordinator.data = MOCK_DEVICE_DATA_HEATER_NUMBER
    await setup_mill_component_number(hass, mock_config_entry, mock_coordinator)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    # Assuming unique_id convention, adjust if different
    number_unique_id = f"{MOCK_DEVICE_ID_HEATER_FOR_NUMBER}_{EDeviceCapability.TARGET_TEMPERATURE.value}"
    temp_number_entity_id = entity_registry.async_get_entity_id("number", DOMAIN, number_unique_id)

    assert temp_number_entity_id is not None
    state = hass.states.get(temp_number_entity_id)
    assert state is not None
    assert state.state == "20.0" # From 'reported' or 'deviceSettings'
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_MIN) == 5 # From MOCK_DEVICE_DATA
    assert state.attributes.get(ATTR_MAX) == 35
    assert state.attributes.get(ATTR_STEP) == 1
    assert state.attributes.get(ATTR_MODE) == NumberMode.AUTO # Or NumberMode.SLIDER / NumberMode.BOX
    # assert state.attributes.get(ATTR_DEVICE_CLASS) == NumberDeviceClass.TEMPERATURE # If applicable


async def test_set_target_temperature_number_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MillDataCoordinator,
    mock_api_client: MillApiClient
):
    """Test setting the value for a target temperature number entity."""
    mock_api_client.get_all_devices.return_value = MOCK_DEVICE_DATA_HEATER_NUMBER
    mock_coordinator.data = MOCK_DEVICE_DATA_HEATER_NUMBER
    await setup_mill_component_number(hass, mock_config_entry, mock_coordinator)

    number_unique_id = f"{MOCK_DEVICE_ID_HEATER_FOR_NUMBER}_{EDeviceCapability.TARGET_TEMPERATURE.value}"
    entity_id = (await hass.helpers.entity_registry.async_get_registry()).async_get_entity_id(
        "number", DOMAIN, number_unique_id
    )
    assert entity_id is not None

    new_temp_value = 23.5
    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {"entity_id": entity_id, ATTR_VALUE: new_temp_value},
        blocking=True,
    )

    mock_api_client.set_number_control.assert_called_once_with(
        MOCK_DEVICE_ID_HEATER_FOR_NUMBER,
        EDeviceCapability.TARGET_TEMPERATURE.value, # or the specific key used by API
        new_temp_value
    )
    mock_coordinator.async_request_refresh.assert_called_once()


# TODO: Add more tests:
# - Test for each NUMBER_TYPE defined in number.py to ensure correct properties.
# - Test number entities for other capabilities (e.g., max power limit if applicable).
# - Test state updates when coordinator.async_update_listeners() is called.
# - Test entities becoming unavailable if the device goes offline.
# - Test entities not being created if specific capability is missing.
# - Test handling of API errors during set_value service call.
# - Test NumberMode (AUTO, SLIDER, BOX) if your entities use different modes.
# - Test entity_category (e.g., CONFIG or DIAGNOSTIC) if applicable.