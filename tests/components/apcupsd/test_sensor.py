"""Test sensors of APCUPSd integration."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.apcupsd.coordinator import REQUEST_REFRESH_COOLDOWN
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import MOCK_STATUS, async_init_integration

from tests.common import async_fire_time_changed


async def test_sensor(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test states of sensor."""
    await async_init_integration(hass, status=MOCK_STATUS)

    # Test a representative string sensor.
    state = hass.states.get("sensor.ups_mode")
    assert state
    assert state.state == "Stand Alone"
    entry = entity_registry.async_get("sensor.ups_mode")
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
    entry = entity_registry.async_get("sensor.ups_input_voltage")
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
    entry = entity_registry.async_get("sensor.ups_battery_voltage")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_battv"

    # test a representative time sensor.
    state = hass.states.get("sensor.ups_self_test_interval")
    assert state
    assert state.state == "7"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.DAYS
    entry = entity_registry.async_get("sensor.ups_self_test_interval")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_stesti"

    # Test a representative percentage sensor.
    state = hass.states.get("sensor.ups_load")
    assert state
    assert state.state == "14.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    entry = entity_registry.async_get("sensor.ups_load")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_loadpct"

    # Test a representative wattage sensor.
    state = hass.states.get("sensor.ups_nominal_output_power")
    assert state
    assert state.state == "330"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    entry = entity_registry.async_get("sensor.ups_nominal_output_power")
    assert entry
    assert entry.unique_id == "XXXXXXXXXXXX_nompower"


async def test_sensor_disabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test sensor disabled by default."""
    await async_init_integration(hass)

    # Test a representative integration-disabled sensor.
    entry = entity_registry.async_get("sensor.ups_model")
    assert entry.disabled
    assert entry.unique_id == "XXXXXXXXXXXX_model"
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity.
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, **{"disabled_by": None}
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False


async def test_state_update(hass: HomeAssistant) -> None:
    """Ensure the sensor state changes after updating the data."""
    await async_init_integration(hass)

    state = hass.states.get("sensor.ups_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "14.0"

    new_status = MOCK_STATUS | {"LOADPCT": "15.0 Percent"}
    with patch("aioapcaccess.request_status", return_value=new_status):
        future = utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.ups_load")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "15.0"


async def test_manual_update_entity(hass: HomeAssistant) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await async_init_integration(hass)

    # Assert the initial state of sensor.ups_load.
    state = hass.states.get("sensor.ups_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "14.0"

    # Setup HASS for calling the update_entity service.
    await async_setup_component(hass, "homeassistant", {})

    with patch("aioapcaccess.request_status") as mock_request_status:
        mock_request_status.return_value = MOCK_STATUS | {
            "LOADPCT": "15.0 Percent",
            "BCHARGE": "99.0 Percent",
        }
        # Now, we fast-forward the time to pass the debouncer cooldown, but put it
        # before the normal update interval to see if the manual update works.
        future = utcnow() + timedelta(seconds=REQUEST_REFRESH_COOLDOWN)
        async_fire_time_changed(hass, future)
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.ups_load", "sensor.ups_battery"]},
            blocking=True,
        )
        # Even if we requested updates for two entities, our integration should smartly
        # group the API calls to just one.
        assert mock_request_status.call_count == 1

        # The new state should be effective.
        state = hass.states.get("sensor.ups_load")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "15.0"


async def test_multiple_manual_update_entity(hass: HomeAssistant) -> None:
    """Test multiple simultaneous manual update entity via service homeassistant/update_entity.

    We should only do network call once for the multiple simultaneous update entity services.
    """
    await async_init_integration(hass)

    # Setup HASS for calling the update_entity service.
    await async_setup_component(hass, "homeassistant", {})

    with patch(
        "aioapcaccess.request_status", return_value=MOCK_STATUS
    ) as mock_request_status:
        # Fast-forward time to just pass the initial debouncer cooldown.
        future = utcnow() + timedelta(seconds=REQUEST_REFRESH_COOLDOWN)
        async_fire_time_changed(hass, future)
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: ["sensor.ups_load", "sensor.ups_input_voltage"]},
            blocking=True,
        )
        assert mock_request_status.call_count == 1
