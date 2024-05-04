"""Sensor tests for the Goalzero integration."""

from homeassistant.components.goalzero.const import DEFAULT_NAME
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant

from . import async_init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry_enabled_by_default: None,
) -> None:
    """Test we get sensor data."""
    await async_init_integration(hass, aioclient_mock)

    state = hass.states.get(f"sensor.{DEFAULT_NAME}_power_in")
    assert state.state == "0.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_current_in")
    assert state.state == "0.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricCurrent.AMPERE
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_power_out")
    assert state.state == "50.5"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_current_out")
    assert state.state == "2.1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.CURRENT
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricCurrent.AMPERE
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_energy_out")
    assert state.state == "5.23"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL_INCREASING
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_energy_stored")
    assert state.state == "1330"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.WATT_HOUR
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.TOTAL
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_voltage")
    assert state.state == "12.0"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricPotential.VOLT
    )
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_state_of_charge_percent")
    assert state.state == "95"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.BATTERY
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_time_to_empty_full")
    assert state.state == "-1"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DURATION
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.MINUTES
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_temperature")
    assert state.state == "25"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.CELSIUS
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_wi_fi_strength")
    assert state.state == "-62"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.SIGNAL_STRENGTH
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == SIGNAL_STRENGTH_DECIBELS
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_total_run_time")
    assert state.state == "1720984"
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.SECONDS
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_wi_fi_ssid")
    assert state.state == "wifi"
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
    state = hass.states.get(f"sensor.{DEFAULT_NAME}_ip_address")
    assert state.state == "1.2.3.4"
    assert state.attributes.get(ATTR_DEVICE_CLASS) is None
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.attributes.get(ATTR_STATE_CLASS) is None
