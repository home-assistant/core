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
    STATE_UNKNOWN,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify
from homeassistant.util.dt import utcnow

from . import MOCK_MINIMAL_STATUS, MOCK_STATUS, async_init_integration

from tests.common import async_fire_time_changed


async def test_sensor(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test states of sensor."""
    await async_init_integration(hass, status=MOCK_STATUS)
    device_slug, serialno = slugify(MOCK_STATUS["UPSNAME"]), MOCK_STATUS["SERIALNO"]

    # Test a representative string sensor.
    state = hass.states.get(f"sensor.{device_slug}_mode")
    assert state
    assert state.state == "Stand Alone"
    entry = entity_registry.async_get(f"sensor.{device_slug}_mode")
    assert entry
    assert entry.unique_id == f"{serialno}_upsmode"

    # Test two representative voltage sensors.
    state = hass.states.get(f"sensor.{device_slug}_input_voltage")
    assert state
    assert state.state == "124.0"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricPotential.VOLT
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    entry = entity_registry.async_get(f"sensor.{device_slug}_input_voltage")
    assert entry
    assert entry.unique_id == f"{serialno}_linev"

    state = hass.states.get(f"sensor.{device_slug}_battery_voltage")
    assert state
    assert state.state == "13.7"
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfElectricPotential.VOLT
    )
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.VOLTAGE
    entry = entity_registry.async_get(f"sensor.{device_slug}_battery_voltage")
    assert entry
    assert entry.unique_id == f"{serialno}_battv"

    # Test a representative time sensor.
    state = hass.states.get(f"sensor.{device_slug}_self_test_interval")
    assert state
    assert state.state == "7"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTime.DAYS
    entry = entity_registry.async_get(f"sensor.{device_slug}_self_test_interval")
    assert entry
    assert entry.unique_id == f"{serialno}_stesti"

    # Test a representative percentage sensor.
    state = hass.states.get(f"sensor.{device_slug}_load")
    assert state
    assert state.state == "14.0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE
    assert state.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    entry = entity_registry.async_get(f"sensor.{device_slug}_load")
    assert entry
    assert entry.unique_id == f"{serialno}_loadpct"

    # Test a representative wattage sensor.
    state = hass.states.get(f"sensor.{device_slug}_nominal_output_power")
    assert state
    assert state.state == "330"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.WATT
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    entry = entity_registry.async_get(f"sensor.{device_slug}_nominal_output_power")
    assert entry
    assert entry.unique_id == f"{serialno}_nompower"


async def test_sensor_name(hass: HomeAssistant) -> None:
    """Test if sensor name follows the recommended entity naming scheme.

    See https://developers.home-assistant.io/docs/core/entity/#entity-naming for more details.
    """
    await async_init_integration(hass, status=MOCK_STATUS)

    all_states = hass.states.async_all()
    assert len(all_states) != 0

    device_name = MOCK_STATUS["UPSNAME"]
    for state in all_states:
        # Friendly name must start with the device name.
        friendly_name = state.name
        assert friendly_name.startswith(device_name)

        # Entity names should start with a capital letter, the rest of the words are lower case.
        entity_name = friendly_name.removeprefix(device_name).strip()
        assert entity_name == entity_name.capitalize()


async def test_sensor_disabled(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test sensor disabled by default."""
    await async_init_integration(hass)

    device_slug, serialno = slugify(MOCK_STATUS["UPSNAME"]), MOCK_STATUS["SERIALNO"]
    # Test a representative integration-disabled sensor.
    entry = entity_registry.async_get(f"sensor.{device_slug}_model")
    assert entry.disabled
    assert entry.unique_id == f"{serialno}_model"
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # Test enabling entity.
    updated_entry = entity_registry.async_update_entity(
        entry.entity_id, disabled_by=None
    )

    assert updated_entry != entry
    assert updated_entry.disabled is False


async def test_state_update(hass: HomeAssistant) -> None:
    """Ensure the sensor state changes after updating the data."""
    await async_init_integration(hass)

    device_slug = slugify(MOCK_STATUS["UPSNAME"])
    state = hass.states.get(f"sensor.{device_slug}_load")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.state == "14.0"

    new_status = MOCK_STATUS | {"LOADPCT": "15.0 Percent"}
    with patch("aioapcaccess.request_status", return_value=new_status):
        future = utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        state = hass.states.get(f"sensor.{device_slug}_load")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "15.0"


async def test_manual_update_entity(hass: HomeAssistant) -> None:
    """Test manual update entity via service homeassistant/update_entity."""
    await async_init_integration(hass)

    device_slug = slugify(MOCK_STATUS["UPSNAME"])
    # Assert the initial state of sensor.ups_load.
    state = hass.states.get(f"sensor.{device_slug}_load")
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
            {
                ATTR_ENTITY_ID: [
                    f"sensor.{device_slug}_load",
                    f"sensor.{device_slug}_battery",
                ]
            },
            blocking=True,
        )
        # Even if we requested updates for two entities, our integration should smartly
        # group the API calls to just one.
        assert mock_request_status.call_count == 1

        # The new state should be effective.
        state = hass.states.get(f"sensor.{device_slug}_load")
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state.state == "15.0"


async def test_multiple_manual_update_entity(hass: HomeAssistant) -> None:
    """Test multiple simultaneous manual update entity via service homeassistant/update_entity.

    We should only do network call once for the multiple simultaneous update entity services.
    """
    await async_init_integration(hass)

    device_slug = slugify(MOCK_STATUS["UPSNAME"])
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
            {
                ATTR_ENTITY_ID: [
                    f"sensor.{device_slug}_load",
                    f"sensor.{device_slug}_input_voltage",
                ]
            },
            blocking=True,
        )
        assert mock_request_status.call_count == 1


async def test_sensor_unknown(hass: HomeAssistant) -> None:
    """Test if our integration can properly certain sensors as unknown when it becomes so."""
    await async_init_integration(hass, status=MOCK_MINIMAL_STATUS)

    ups_mode_id = "sensor.apc_ups_mode"
    last_self_test_id = "sensor.apc_ups_last_self_test"

    assert hass.states.get(ups_mode_id).state == MOCK_MINIMAL_STATUS["UPSMODE"]
    # Last self test sensor should be added even if our status does not report it initially (it is
    # a sensor that appears only after a periodical or manual self test is performed).
    assert hass.states.get(last_self_test_id) is not None
    assert hass.states.get(last_self_test_id).state == STATE_UNKNOWN

    # Simulate an event (a self test) such that "LASTSTEST" field is being reported, the state of
    # the sensor should be properly updated with the corresponding value.
    with patch("aioapcaccess.request_status") as mock_request_status:
        mock_request_status.return_value = MOCK_MINIMAL_STATUS | {
            "LASTSTEST": "1970-01-01 00:00:00 0000"
        }
        future = utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
    assert hass.states.get(last_self_test_id).state == "1970-01-01 00:00:00 0000"

    # Simulate another event (e.g., daemon restart) such that "LASTSTEST" is no longer reported.
    with patch("aioapcaccess.request_status") as mock_request_status:
        mock_request_status.return_value = MOCK_MINIMAL_STATUS
        future = utcnow() + timedelta(minutes=2)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
    # The state should become unknown again.
    assert hass.states.get(last_self_test_id).state == STATE_UNKNOWN
