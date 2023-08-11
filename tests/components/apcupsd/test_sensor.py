"""Test sensors of APCUPSd integration."""

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_STATUS, async_init_integration


async def test_sensor(hass: HomeAssistant) -> None:
    """Test states of sensor."""
    await async_init_integration(hass, status=MOCK_STATUS)
    registry = er.async_get(hass)

    # Test a representative string sensor.
    state = hass.states.get("sensor.ups_mode")
    assert state
    assert state.state == "Stand Alone"
    entry = registry.async_get("sensor.ups_mode")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_upsmode"

    # Test two representative voltage sensors.
    state = hass.states.get("sensor.ups_input_voltage")
    assert state
    assert state.state == "124.0"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricPotential.VOLT
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    entry = registry.async_get("sensor.ups_input_voltage")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_linev"

    state = hass.states.get("sensor.ups_battery_voltage")
    assert state
    assert state.state == "13.7"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricPotential.VOLT
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    entry = registry.async_get("sensor.ups_battery_voltage")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_battv"

    # test a representative time sensor.
    state = hass.states.get("sensor.ups_self_test_interval")
    assert state
    assert state.state == "7"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.DAYS
    entry = registry.async_get("sensor.ups_self_test_interval")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_stesti"

    # Test a representative percentage sensor.
    state = hass.states.get("sensor.ups_load")
    assert state
    assert state.state == "14.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    entry = registry.async_get("sensor.ups_load")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_loadpct"

    # Test a representative wattage sensor.
    state = hass.states.get("sensor.ups_nominal_output_power")
    assert state
    assert state.state == "330"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    entry = registry.async_get("sensor.ups_nominal_output_power")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_nompower"


async def test_sensor_disabled(hass: HomeAssistant) -> None:
    """Test sensor disabled by default."""
    await async_init_integration(hass)
    registry = er.async_get(hass)

    # Test a representative integration-disabled sensor.
    entry = registry.async_get("sensor.ups_model")
    assert entry.disabled
    assert entry.unique_id == "XXXXXXXXXXXX_model"
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity.
    updated_entry = registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False
