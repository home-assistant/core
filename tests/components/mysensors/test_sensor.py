"""Provide tests for mysensors sensor platform."""

from __future__ import annotations

from collections.abc import Callable

from mysensors.sensor import Sensor
import pytest

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from tests.common import MockConfigEntry


async def test_gps_sensor(
    hass: HomeAssistant,
    gps_sensor: Sensor,
    receive_message: Callable[[str], None],
) -> None:
    """Test a gps sensor."""
    entity_id = "sensor.gps_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "40.741894,-73.989311,12"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0

    altitude = 0
    new_coords = "40.782,-73.965"
    message_string = f"1;1;1;0;49;{new_coords},{altitude}\n"

    receive_message(message_string)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == f"{new_coords},{altitude}"


async def test_ir_transceiver(
    hass: HomeAssistant,
    ir_transceiver: Sensor,
    receive_message: Callable[[str], None],
) -> None:
    """Test an ir transceiver."""
    entity_id = "sensor.ir_transceiver_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "test_code"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0

    receive_message("1;1;1;0;50;new_code\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "new_code"


async def test_battery_entity(
    hass: HomeAssistant,
    battery_sensor: Sensor,
    receive_message: Callable[[str], None],
) -> None:
    """Test sensor with battery level reporting."""
    battery_entity_id = "sensor.battery_sensor_1_battery"
    state = hass.states.get(battery_entity_id)
    assert state
    assert state.state == "42"
    assert ATTR_BATTERY_LEVEL not in state.attributes

    receive_message("1;255;3;0;0;84\n")
    await hass.async_block_till_done()

    state = hass.states.get(battery_entity_id)
    assert state
    assert state.state == "84"
    assert ATTR_BATTERY_LEVEL not in state.attributes


async def test_power_sensor(
    hass: HomeAssistant,
    power_sensor: Sensor,
    integration: MockConfigEntry,
) -> None:
    """Test a power sensor."""
    entity_id = "sensor.power_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "1200"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.POWER
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.WATT
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0


async def test_energy_sensor(
    hass: HomeAssistant,
    energy_sensor: Sensor,
    integration: MockConfigEntry,
) -> None:
    """Test an energy sensor."""
    entity_id = "sensor.energy_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "18000"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL_INCREASING
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0


async def test_sound_sensor(
    hass: HomeAssistant,
    sound_sensor: Sensor,
    integration: MockConfigEntry,
) -> None:
    """Test a sound sensor."""
    entity_id = "sensor.sound_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "10"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.SOUND_PRESSURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "dB"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0


async def test_distance_sensor(
    hass: HomeAssistant,
    distance_sensor: Sensor,
    integration: MockConfigEntry,
) -> None:
    """Test a distance sensor."""
    entity_id = "sensor.distance_sensor_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "15"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.DISTANCE
    assert ATTR_ICON not in state.attributes
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "cm"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0


@pytest.mark.parametrize(
    ("unit_system", "unit"),
    [
        (METRIC_SYSTEM, UnitOfTemperature.CELSIUS),
        (US_CUSTOMARY_SYSTEM, UnitOfTemperature.FAHRENHEIT),
    ],
)
async def test_temperature_sensor(
    hass: HomeAssistant,
    temperature_sensor: Sensor,
    receive_message: Callable[[str], None],
    unit_system: UnitSystem,
    unit: str,
) -> None:
    """Test a temperature sensor."""
    entity_id = "sensor.temperature_sensor_1_1"
    hass.config.units = unit_system
    temperature = "22.0"
    message_string = f"1;1;1;0;0;{temperature}\n"

    receive_message(message_string)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == temperature
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.TEMPERATURE
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == unit
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0
