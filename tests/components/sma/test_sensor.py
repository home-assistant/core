"""Test the sma sensor platform."""

from pysma.const import (
    ENERGY_METER_VIA_INVERTER,
    GENERIC_SENSORS,
    OPTIMIZERS_VIA_INVERTER,
)
from pysma.definitions import sensor_map

from homeassistant.components.sma.sensor import SENSOR_ENTITIES
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfPower
from homeassistant.core import HomeAssistant


async def test_sensors(hass: HomeAssistant, init_integration) -> None:
    """Test states of the sensors."""
    state = hass.states.get("sensor.sma_device_grid_power")
    assert state
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT


async def test_sensor_entities(hass: HomeAssistant, init_integration) -> None:
    """Test SENSOR_ENTITIES contains a SensorEntityDescription for each pysma sensor."""
    pysma_sensor_definitions = (
        sensor_map[GENERIC_SENSORS]
        + sensor_map[OPTIMIZERS_VIA_INVERTER]
        + sensor_map[ENERGY_METER_VIA_INVERTER]
    )

    for sensor in pysma_sensor_definitions:
        assert sensor.name in SENSOR_ENTITIES
