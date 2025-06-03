"""Tests for the Mill Sensor platform."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    ATTR_DEVICE_CLASS,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfEnergy,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
    ATTR_STATE_CLASS,
)

from homeassistant.setup import async_setup_component
from homeassistant.helpers.entity_registry import EntityRegistry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mill_wifi.const import DOMAIN
from custom_components.mill_wifi.coordinator import MillDataCoordinator
from custom_components.mill_wifi.api import MillApiClient
from custom_components.mill_wifi.sensor import SENSOR_TYPES
from custom_components.mill_wifi.device_capability import EDeviceCapability, EDeviceType

# Sample device data - this should be expanded to cover various sensor scenarios
# This particular device is a Mill Gen 3 Heater, which can provide temperature
MOCK_DEVICE_ID_HEATER = "heater_device_123"
MOCK_DEVICE_DATA_HEATER = {
    MOCK_DEVICE_ID_HEATER: {
        "deviceId": MOCK_DEVICE_ID_HEATER,
        "deviceName": "Living Room Heater",
        "houseId": "house_1",
        "type": EDeviceType.PANEL_HEATER_GEN3.value,
        "isHeating": 1,
        "currentTemperature": 21.5,
        "targetTemperature": 22.0,
        "fanStatus": 1,
        "powerStatus": 1,
        "capabilities": [EDeviceCapability.MEASURE_TEMPERATURE.value], # Uses enum value
        "deviceSettings": {"temperatureNormal": 22},
        "lastMetrics": {"temperature": 21.5},
        "reported": {"temperature": 21.5, "powerState": "on"},
    }
}

# Sample data for a device with multiple sensors (e.g., an Air Purifier)
MOCK_DEVICE_ID_PURIFIER = "purifier_device_456"
MOCK_DEVICE_DATA_PURIFIER = {
    MOCK_DEVICE_ID_PURIFIER: {
        "deviceId": MOCK_DEVICE_ID_PURIFIER,
        "deviceName": "Bedroom Purifier",
        "houseId": "house_1",
        "type": EDeviceType.AIR_PURIFIER_M.value, # Adjust if a different type exists
        "powerStatus": 1,
        "capabilities": [
            EDeviceCapability.MEASURE_HUMIDITY.value,
            EDeviceCapability.MEASURE_TVOC.value,
            EDeviceCapability.MEASURE_CO2.value,
            EDeviceCapability.MEASURE_PM25.value,
            EDeviceCapability.MEASURE_PM10.value, # Assuming PM10 capability
            EDeviceCapability.MEASURE_FILTER_STATE.value,
        ],
        "lastMetrics": {
            "humidity": 45.0,
            "tvoc": 150.0, # Assuming ppb for TVOC from SENSOR_TYPES
            "eco2": 500.0, # Assuming ppm for CO2
            "pm25": 10.0,
            "pm10": 12.0,
            "filterRemaining": 85.0, # Assuming percentage
        },
        "reported": {"powerState": "on"},
    }
}

@pytest.fixture # In test_sensor.py
def mock_api_client():
    client = AsyncMock(spec=MillApiClient)
    client.connect = AsyncMock(return_value=True)
    client.get_all_devices = AsyncMock(return_value=[]) # Default or specific mock data
    return client


@pytest.fixture
async def mock_coordinator(hass: HomeAssistant, mock_api_client: MillApiClient):
    """Fixture for a mock MillDataCoordinator."""
    coordinator = MillDataCoordinator(hass, mock_api_client)
    coordinator.data = {} # Default to empty
    return coordinator

@pytest.fixture
def mock_config_entry():
    """Fixture for a mock ConfigEntry."""
    return MockConfigEntry(domain=DOMAIN, data={"username": "test_user", "password": "test_password"})


async def setup_mill_component(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    coordinator: MillDataCoordinator
):
    """Set up the Mill component for testing sensors."""
    config_entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    # Forward platform setup
    # This assumes your __init__.py forwards to sensor platform like:
    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # If your setup is different, this might need adjustment.
    # For direct platform setup test:
    with patch("custom_components.mill_wifi.PLATFORMS", ["sensor"]):
         await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_no_sensors_if_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MillDataCoordinator
):
    """Test that no sensors are created if there are no devices or no data."""
    mock_coordinator.data = {} # Ensure coordinator has no data
    await setup_mill_component(hass, mock_config_entry, mock_coordinator)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    assert len(entity_registry.entities) == 0


async def test_temperature_sensor_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MillDataCoordinator,
    mock_api_client: MillApiClient
):
    """Test creation of a temperature sensor for a Mill Heater."""
    mock_api_client.get_all_devices.return_value = MOCK_DEVICE_DATA_HEATER
    mock_coordinator.data = MOCK_DEVICE_DATA_HEATER # Set coordinator data
    await setup_mill_component(hass, mock_config_entry, mock_coordinator)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    sensor_unique_id = f"{MOCK_DEVICE_ID_HEATER}_{EDeviceCapability.MEASURE_TEMPERATURE.value}"
    temp_sensor_entity = entity_registry.async_get_entity_id("sensor", DOMAIN, sensor_unique_id)

    assert temp_sensor_entity is not None
    state = hass.states.get(temp_sensor_entity)
    assert state is not None
    assert state.state == "21.5"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT


# Example for a more complex device (like an Air Purifier)
async def test_air_purifier_sensors_creation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_coordinator: MillDataCoordinator,
    mock_api_client: MillApiClient
):
    """Test creation of multiple sensors for an Air Purifier."""
    mock_api_client.get_all_devices.return_value = MOCK_DEVICE_DATA_PURIFIER
    mock_coordinator.data = MOCK_DEVICE_DATA_PURIFIER
    await setup_mill_component(hass, mock_config_entry, mock_coordinator)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # Check Humidity Sensor
    humidity_sensor_id = f"{MOCK_DEVICE_ID_PURIFIER}_{EDeviceCapability.MEASURE_HUMIDITY.value}"
    humidity_entity = entity_registry.async_get_entity_id("sensor", DOMAIN, humidity_sensor_id)
    assert humidity_entity is not None
    state = hass.states.get(humidity_entity)
    assert state.state == "45.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.HUMIDITY
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    # Check CO2 Sensor
    co2_sensor_id = f"{MOCK_DEVICE_ID_PURIFIER}_{EDeviceCapability.MEASURE_IAQ_CO2.value}"
    co2_entity = entity_registry.async_get_entity_id("sensor", DOMAIN, co2_sensor_id)
    assert co2_entity is not None
    state = hass.states.get(co2_entity)
    assert state.state == "500.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == CONCENTRATION_PARTS_PER_MILLION
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CO2
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    # Check TVOC Sensor (ppb is not a direct HA Unit, so it might be unitless or custom)
    # Unit might be CONCENTRATION_MICROGRAMS_PER_CUBIC_METER if conversion happens
    # Or it could be unitless with device_class VOC
    tvoc_sensor_id = f"{MOCK_DEVICE_ID_PURIFIER}_{EDeviceCapability.MEASURE_IAQ_VOC.value}"
    tvoc_entity = entity_registry.async_get_entity_id("sensor", DOMAIN, tvoc_sensor_id)
    assert tvoc_entity is not None
    state = hass.states.get(tvoc_entity)
    assert state.state == "150.0"
    # Assuming SENSOR_TYPES maps VOC to SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
    # and potentially a unit if one is assigned in SENSOR_TYPES
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS
    # assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "ppb" # or whatever is defined

    # Check PM2.5 Sensor
    pm25_sensor_id = f"{MOCK_DEVICE_ID_PURIFIER}_{EDeviceCapability.MEASURE_IAQ_PM25.value}"
    pm25_entity = entity_registry.async_get_entity_id("sensor", DOMAIN, pm25_sensor_id)
    assert pm25_entity is not None
    state = hass.states.get(pm25_entity)
    assert state.state == "10.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.PM25
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    # Check Filter State Sensor
    filter_sensor_id = f"{MOCK_DEVICE_ID_PURIFIER}_{EDeviceCapability.FILTER_STATE.value}"
    filter_entity = entity_registry.async_get_entity_id("sensor", DOMAIN, filter_sensor_id)
    assert filter_entity is not None
    state = hass.states.get(filter_entity)
    assert state.state == "85.0" # Assuming it's a percentage
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    # No specific device class for filter state, icon might be used instead


# TODO: Add more tests:
# - Test for each SENSOR_TYPE defined in sensor.py to ensure correct properties
#   (device_class, state_class, unit, icon).
# - Test sensor state updates when coordinator.async_update_listeners() is called.
# - Test sensors becoming unavailable if the device goes offline in coordinator data.
# - Test sensors not being created if the specific capability is missing from device data.
# - Test sensors handling missing values from the API (e.g., should they report 'unknown'?).