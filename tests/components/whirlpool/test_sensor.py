"""Test the Whirlpool Sensor domain."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

from whirlpool.washerdryer import MachineState

from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import as_timestamp, utc_from_timestamp

from . import init_integration

from tests.common import mock_restore_cache_with_extra_data


async def update_sensor_state(
    hass: HomeAssistant,
    entity_id: str,
    mock_sensor_api_instance: MagicMock,
) -> State:
    """Simulate an update trigger from the API."""

    for call in mock_sensor_api_instance.register_attr_callback.call_args_list:
        update_ha_state_cb = call[0][0]
        update_ha_state_cb()
        await hass.async_block_till_done()

    return hass.states.get(entity_id)


def side_effect_function_open_door(*args, **kwargs):
    """Return correct value for attribute."""
    if args[0] == "Cavity_TimeStatusEstTimeRemaining":
        return 3540

    if args[0] == "Cavity_OpStatusDoorOpen":
        return "1"

    if args[0] == "WashCavity_OpStatusBulkDispense1Level":
        return "3"


async def test_dryer_sensor_values(
    hass: HomeAssistant,
    mock_sensor_api_instances: MagicMock,
    mock_sensor2_api: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor value callbacks."""
    hass.state = CoreState.not_running
    thetimestamp: datetime = datetime(2022, 11, 29, 00, 00, 00, 00, timezone.utc)
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "sensor.washer_end_time",
                    "1",
                ),
                {"native_value": thetimestamp, "native_unit_of_measurement": None},
            ),
            (
                State("sensor.dryer_end_time", "1"),
                {"native_value": thetimestamp, "native_unit_of_measurement": None},
            ),
        ),
    )

    await init_integration(hass)

    entity_id = "sensor.dryer_state"
    mock_instance = mock_sensor2_api
    entry = entity_registry.async_get(entity_id)
    assert entry
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "standby"

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    state_id = f"{entity_id.split('_')[0]}_end_time"
    state = hass.states.get(state_id)
    assert state.state == thetimestamp.isoformat()

    mock_instance.get_machine_state.return_value = MachineState.RunningMainCycle
    mock_instance.get_cycle_status_filling.return_value = False
    mock_instance.attr_value_to_bool.side_effect = [
        False,
        False,
        False,
        False,
        False,
        False,
    ]

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "running_maincycle"

    mock_instance.get_machine_state.return_value = MachineState.Complete

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "complete"


async def test_washer_sensor_values(
    hass: HomeAssistant,
    mock_sensor_api_instances: MagicMock,
    mock_sensor1_api: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor value callbacks."""
    hass.state = CoreState.not_running
    thetimestamp: datetime = datetime(2022, 11, 29, 00, 00, 00, 00, timezone.utc)
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "sensor.washer_end_time",
                    "1",
                ),
                {"native_value": thetimestamp, "native_unit_of_measurement": None},
            ),
            (
                State("sensor.dryer_end_time", "1"),
                {"native_value": thetimestamp, "native_unit_of_measurement": None},
            ),
        ),
    )

    await init_integration(hass)

    entity_id = "sensor.washer_state"
    mock_instance = mock_sensor1_api
    entry = entity_registry.async_get(entity_id)
    assert entry
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "standby"

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    state_id = f"{entity_id.split('_')[0]}_end_time"
    state = hass.states.get(state_id)
    assert state.state == thetimestamp.isoformat()

    state_id = f"{entity_id.split('_')[0]}_detergent_level"
    entry = entity_registry.async_get(state_id)
    assert entry
    assert entry.disabled
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    update_entry = entity_registry.async_update_entity(
        entry.entity_id, disabled_by=None
    )
    await hass.async_block_till_done()

    assert update_entry != entry
    assert update_entry.disabled is False
    state = hass.states.get(state_id)
    assert state is None

    await hass.config_entries.async_reload(entry.config_entry_id)
    state = hass.states.get(state_id)
    assert state is not None
    assert state.state == "50"

    # Test the washer cycle states
    mock_instance.get_machine_state.return_value = MachineState.RunningMainCycle
    mock_instance.get_cycle_status_filling.return_value = True
    mock_instance.attr_value_to_bool.side_effect = [
        True,
        False,
        False,
        False,
        False,
        False,
    ]

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "cycle_filling"

    mock_instance.get_cycle_status_filling.return_value = False
    mock_instance.get_cycle_status_rinsing.return_value = True
    mock_instance.attr_value_to_bool.side_effect = [
        False,
        True,
        False,
        False,
        False,
        False,
    ]

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "cycle_rinsing"

    mock_instance.get_cycle_status_rinsing.return_value = False
    mock_instance.get_cycle_status_sensing.return_value = True
    mock_instance.attr_value_to_bool.side_effect = [
        False,
        False,
        True,
        False,
        False,
        False,
    ]

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "cycle_sensing"

    mock_instance.get_cycle_status_sensing.return_value = False
    mock_instance.get_cycle_status_soaking.return_value = True
    mock_instance.attr_value_to_bool.side_effect = [
        False,
        False,
        False,
        True,
        False,
        False,
    ]

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "cycle_soaking"

    mock_instance.get_cycle_status_soaking.return_value = False
    mock_instance.get_cycle_status_spinning.return_value = True
    mock_instance.attr_value_to_bool.side_effect = [
        False,
        False,
        False,
        False,
        True,
        False,
    ]

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "cycle_spinning"

    mock_instance.get_cycle_status_spinning.return_value = False
    mock_instance.get_cycle_status_washing.return_value = True
    mock_instance.attr_value_to_bool.side_effect = [
        False,
        False,
        False,
        False,
        False,
        True,
    ]

    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "cycle_washing"

    mock_instance.get_machine_state.return_value = MachineState.Complete
    mock_instance.attr_value_to_bool.side_effect = None
    mock_instance.get_attribute.side_effect = side_effect_function_open_door
    state = await update_sensor_state(hass, entity_id, mock_instance)
    assert state is not None
    assert state.state == "door_open"


async def test_restore_state(
    hass: HomeAssistant,
    mock_sensor_api_instances: MagicMock,
) -> None:
    """Test sensor restore state."""
    # Home assistant is not running yet
    hass.state = CoreState.not_running
    thetimestamp: datetime = datetime(2022, 11, 29, 00, 00, 00, 00, timezone.utc)
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "sensor.washer_end_time",
                    "1",
                ),
                {"native_value": thetimestamp, "native_unit_of_measurement": None},
            ),
            (
                State("sensor.dryer_end_time", "1"),
                {"native_value": thetimestamp, "native_unit_of_measurement": None},
            ),
        ),
    )

    # create and add entry
    await init_integration(hass)
    # restore from cache
    state = hass.states.get("sensor.washer_end_time")
    assert state.state == thetimestamp.isoformat()
    state = hass.states.get("sensor.dryer_end_time")
    assert state.state == thetimestamp.isoformat()


async def test_no_restore_state(
    hass: HomeAssistant,
    mock_sensor_api_instances: MagicMock,
    mock_sensor1_api: MagicMock,
) -> None:
    """Test sensor restore state with no restore."""
    # create and add entry
    entity_id = "sensor.washer_end_time"
    await init_integration(hass)
    # restore from cache
    state = hass.states.get(entity_id)
    assert state.state == "unknown"

    mock_sensor1_api.get_machine_state.return_value = MachineState.RunningMainCycle
    state = await update_sensor_state(hass, entity_id, mock_sensor1_api)
    assert state.state != "unknown"


async def test_callback(
    hass: HomeAssistant,
    mock_sensor_api_instances: MagicMock,
    mock_sensor1_api: MagicMock,
) -> None:
    """Test callback timestamp callback function."""
    hass.state = CoreState.not_running
    thetimestamp: datetime = datetime(2022, 11, 29, 00, 00, 00, 00, timezone.utc)
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(
                    "sensor.washer_end_time",
                    "1",
                ),
                {"native_value": thetimestamp, "native_unit_of_measurement": None},
            ),
            (
                State("sensor.dryer_end_time", "1"),
                {"native_value": thetimestamp, "native_unit_of_measurement": None},
            ),
        ),
    )

    # create and add entry
    await init_integration(hass)
    # restore from cache
    state = hass.states.get("sensor.washer_end_time")
    assert state.state == thetimestamp.isoformat()
    callback = mock_sensor1_api.register_attr_callback.call_args_list[1][0][0]
    callback()

    state = hass.states.get("sensor.washer_end_time")
    assert state.state == thetimestamp.isoformat()
    mock_sensor1_api.get_machine_state.return_value = MachineState.RunningMainCycle
    mock_sensor1_api.get_attribute.side_effect = None
    mock_sensor1_api.get_attribute.return_value = "60"
    callback()

    # Test new timestamp when machine starts a cycle.
    state = hass.states.get("sensor.washer_end_time")
    time = state.state
    assert state.state != thetimestamp.isoformat()

    # Test no timestamp change for < 60 seconds time change.
    mock_sensor1_api.get_attribute.return_value = "65"
    callback()
    state = hass.states.get("sensor.washer_end_time")
    assert state.state == time

    # Test timestamp change for > 60 seconds.
    mock_sensor1_api.get_attribute.return_value = "120"
    callback()
    state = hass.states.get("sensor.washer_end_time")
    newtime = utc_from_timestamp(as_timestamp(time) + 60)
    assert state.state == newtime.isoformat()
