"""Test setting up sensors."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import INPUT_SENSOR, OUTPUT_SENSOR

from tests.common import async_fire_time_changed


async def test_sensor_type_input(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_iotawatt
) -> None:
    """Test input sensors work."""
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 0

    # Discover this sensor during a regular update.
    mock_iotawatt.getSensors.return_value["sensors"]["my_sensor_key"] = INPUT_SENSOR
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    state = hass.states.get("sensor.my_sensor")
    assert state is not None
    assert state.state == "23"
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.MEASUREMENT
    assert state.attributes[ATTR_FRIENDLY_NAME] == "My Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfPower.WATT
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.POWER
    assert state.attributes["channel"] == "1"
    assert state.attributes["type"] == "Input"

    mock_iotawatt.getSensors.return_value["sensors"].pop("my_sensor_key")
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_sensor") is None


async def test_sensor_type_output(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_iotawatt
) -> None:
    """Tests the sensor type of Output."""
    mock_iotawatt.getSensors.return_value["sensors"]["my_watthour_sensor_key"] = (
        OUTPUT_SENSOR
    )
    assert await async_setup_component(hass, "iotawatt", {})
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    state = hass.states.get("sensor.my_watthour_sensor")
    assert state is not None
    assert state.state == "243"
    assert state.attributes[ATTR_STATE_CLASS] is SensorStateClass.TOTAL
    assert state.attributes[ATTR_FRIENDLY_NAME] == "My WattHour Sensor"
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfEnergy.WATT_HOUR
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.ENERGY
    assert state.attributes["type"] == "Output"

    mock_iotawatt.getSensors.return_value["sensors"].pop("my_watthour_sensor_key")
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_watthour_sensor") is None
