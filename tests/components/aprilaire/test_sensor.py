"""Tests for the Aprilaire sensor entity."""

from unittest.mock import MagicMock

from pyaprilaire.const import Attribute

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

from .conftest import setup_integration

# Entity IDs are auto-generated based on device name + entity count
# Indoor humidity sensor
INDOOR_HUMIDITY = "sensor.test_thermostat"
# Outdoor humidity sensor
OUTDOOR_HUMIDITY = "sensor.test_thermostat_2"
# Indoor temperature sensor
INDOOR_TEMP = "sensor.test_thermostat_3"
# Outdoor temperature sensor
OUTDOOR_TEMP = "sensor.test_thermostat_4"
# Dehumidification status
DEHUMIDIFICATION = "sensor.test_thermostat_5"
# Humidification status
HUMIDIFICATION = "sensor.test_thermostat_6"
# Ventilation status
VENTILATION = "sensor.test_thermostat_7"
# Air cleaning status
AIR_CLEANING = "sensor.test_thermostat_8"
# Fan status
FAN_STATUS = "sensor.test_thermostat_9"


async def test_humidity_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test humidity sensor entities."""
    await setup_integration(hass, mock_config_entry)

    indoor = hass.states.get(INDOOR_HUMIDITY)
    assert indoor is not None
    assert indoor.state == "45"
    assert indoor.attributes["device_class"] == SensorDeviceClass.HUMIDITY
    assert indoor.attributes["unit_of_measurement"] == "%"

    outdoor = hass.states.get(OUTDOOR_HUMIDITY)
    assert outdoor is not None
    assert outdoor.state == "60"


async def test_temperature_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test temperature sensor entities."""
    await setup_integration(hass, mock_config_entry)

    indoor = hass.states.get(INDOOR_TEMP)
    assert indoor is not None
    assert indoor.state == "22.5"
    assert indoor.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert indoor.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS

    outdoor = hass.states.get(OUTDOOR_TEMP)
    assert outdoor is not None
    assert outdoor.state == "15.0"


async def test_status_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
) -> None:
    """Test status sensor entities."""
    await setup_integration(hass, mock_config_entry)

    # Dehumidification status = 2 -> "on"
    dehumid = hass.states.get(DEHUMIDIFICATION)
    assert dehumid is not None
    assert dehumid.state == "on"
    assert dehumid.attributes["device_class"] == SensorDeviceClass.ENUM

    # Humidification status = 2 -> "on"
    humid = hass.states.get(HUMIDIFICATION)
    assert humid is not None
    assert humid.state == "on"

    # Ventilation status = 2 -> "on"
    vent = hass.states.get(VENTILATION)
    assert vent is not None
    assert vent.state == "on"

    # Air cleaning status = 2 -> "on"
    air = hass.states.get(AIR_CLEANING)
    assert air is not None
    assert air.state == "on"

    # Fan status = 1 -> "on"
    fan = hass.states.get(FAN_STATUS)
    assert fan is not None
    assert fan.state == "on"


async def test_status_sensor_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test status sensors show idle state."""
    base_coordinator_data[Attribute.HUMIDIFICATION_STATUS] = 0
    base_coordinator_data[Attribute.DEHUMIDIFICATION_STATUS] = 0
    base_coordinator_data[Attribute.VENTILATION_STATUS] = 0
    base_coordinator_data[Attribute.AIR_CLEANING_STATUS] = 0
    base_coordinator_data[Attribute.FAN_STATUS] = 0
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HUMIDIFICATION).state == "idle"
    assert hass.states.get(DEHUMIDIFICATION).state == "idle"
    assert hass.states.get(VENTILATION).state == "idle"
    assert hass.states.get(AIR_CLEANING).state == "idle"
    assert hass.states.get(FAN_STATUS).state == "off"


async def test_status_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test status sensors show off state."""
    base_coordinator_data[Attribute.HUMIDIFICATION_STATUS] = 3
    base_coordinator_data[Attribute.DEHUMIDIFICATION_STATUS] = 4
    base_coordinator_data[Attribute.VENTILATION_STATUS] = 6
    base_coordinator_data[Attribute.AIR_CLEANING_STATUS] = 3
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HUMIDIFICATION).state == "off"
    assert hass.states.get(DEHUMIDIFICATION).state == "off"
    assert hass.states.get(VENTILATION).state == "off"
    assert hass.states.get(AIR_CLEANING).state == "off"


async def test_sensor_not_created_when_status_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test sensors aren't created when their status key indicates unavailability."""
    # Set sensor status to value not in exists list
    base_coordinator_data[Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS] = 99
    base_coordinator_data[Attribute.OUTDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS] = 99
    base_coordinator_data[Attribute.INDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS] = 99
    base_coordinator_data[Attribute.OUTDOOR_TEMPERATURE_CONTROLLING_SENSOR_STATUS] = 99
    # Status sensors check status_sensor_exists_values [1, 2]
    # so available=0 means they don't exist
    base_coordinator_data[Attribute.DEHUMIDIFICATION_AVAILABLE] = 0
    base_coordinator_data[Attribute.HUMIDIFICATION_AVAILABLE] = 0
    base_coordinator_data[Attribute.VENTILATION_AVAILABLE] = 0
    base_coordinator_data[Attribute.AIR_CLEANING_AVAILABLE] = 0
    await setup_integration(hass, mock_config_entry)

    # Only the fan status sensor should be created (it has no status_key filter)
    # All humidity, temperature, and status sensors with unavailable status
    # should be filtered out
    sensor_states = [
        state
        for state in hass.states.async_all("sensor")
        if state.entity_id.startswith("sensor.test_thermostat")
    ]
    assert len(sensor_states) == 1
    # The only sensor should be the fan status sensor
    assert sensor_states[0].attributes["device_class"] == SensorDeviceClass.ENUM
    assert set(sensor_states[0].attributes["options"]) == {"on", "off"}


async def test_sensor_unavailable_when_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test sensors show unavailable when device is disconnected."""
    base_coordinator_data[Attribute.CONNECTED] = False
    base_coordinator_data[Attribute.RECONNECTING] = False
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(INDOOR_HUMIDITY)
    assert state is not None
    assert state.state == "unavailable"


async def test_humidity_sensor_available_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aprilaire: MagicMock,
    base_coordinator_data: dict,
) -> None:
    """Test humidity sensor availability based on status key."""
    # Status 1 means sensor exists but not available (not status 0)
    base_coordinator_data[Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_STATUS] = 1
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(INDOOR_HUMIDITY)
    assert state is not None
    assert state.state == "unavailable"
