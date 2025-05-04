"""Test the Whirlpool Sensor domain."""

from datetime import UTC, datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion
from whirlpool.washerdryer import MachineState

from homeassistant.components.whirlpool.sensor import SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import as_timestamp, utc_from_timestamp, utcnow

from . import init_integration, snapshot_whirlpool_entities, trigger_attr_callback

from tests.common import async_fire_time_changed, mock_restore_cache_with_extra_data

WASHER_ENTITY_ID_BASE = "sensor.washer"
DRYER_ENTITY_ID_BASE = "sensor.dryer"


# Freeze time for WasherDryerTimeSensor
@pytest.mark.freeze_time("2025-05-04 12:00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    await init_integration(hass)
    snapshot_whirlpool_entities(hass, entity_registry, snapshot, Platform.SENSOR)


@pytest.mark.parametrize(
    ("entity_id", "mock_fixture"),
    [
        ("sensor.washer_end_time", "mock_washer_api"),
        ("sensor.dryer_end_time", "mock_dryer_api"),
    ],
)
@pytest.mark.freeze_time("2022-11-30 00:00:00")
async def test_washer_dryer_time_sensor(
    hass: HomeAssistant,
    entity_id: str,
    mock_fixture: str,
    request: pytest.FixtureRequest,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Washer/Dryer end time sensors."""
    now = utcnow()
    restored_datetime: datetime = datetime(2022, 11, 29, 00, 00, 00, 00, UTC)
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(entity_id, "1"),
                {"native_value": restored_datetime, "native_unit_of_measurement": None},
            )
        ],
    )

    mock_instance = request.getfixturevalue(mock_fixture)
    mock_instance.get_machine_state.return_value = MachineState.Pause
    await init_integration(hass)

    # Test restored state.
    state = hass.states.get(entity_id)
    assert state.state == restored_datetime.isoformat()

    # Test no time change because the machine is not running.
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    assert state.state == restored_datetime.isoformat()

    # Test new time when machine starts a cycle.
    mock_instance.get_machine_state.return_value = MachineState.RunningMainCycle
    mock_instance.get_time_remaining.return_value = 60
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    expected_time = (now + timedelta(seconds=60)).isoformat()
    assert state.state == expected_time

    # Test no state change for < 60 seconds elapsed time.
    mock_instance.get_time_remaining.return_value = 65
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    assert state.state == expected_time

    # Test timestamp change for > 60 seconds.
    mock_instance.get_time_remaining.return_value = 125
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    assert (
        state.state == utc_from_timestamp(as_timestamp(expected_time) + 65).isoformat()
    )

    # Test that periodic updates call the API to fetch data
    mock_instance.fetch_data.reset_mock()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_instance.fetch_data.assert_called_once()


@pytest.mark.parametrize(
    ("entity_id", "mock_fixture"),
    [
        ("sensor.washer_end_time", "mock_washer_api"),
        ("sensor.dryer_end_time", "mock_dryer_api"),
    ],
)
@pytest.mark.freeze_time("2022-11-30 00:00:00")
async def test_washer_dryer_time_sensor_no_restore(
    hass: HomeAssistant,
    entity_id: str,
    mock_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test Washer/Dryer end time sensors without state restore."""
    now = utcnow()

    mock_instance = request.getfixturevalue(mock_fixture)
    mock_instance.get_machine_state.return_value = MachineState.Pause
    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN

    # Test no change because the machine is paused.
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN

    # Test new time when machine starts a cycle.
    mock_instance.get_machine_state.return_value = MachineState.RunningMainCycle
    mock_instance.get_time_remaining.return_value = 60
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    expected_time = (now + timedelta(seconds=60)).isoformat()
    assert state.state == expected_time


@pytest.mark.parametrize(
    ("entity_id", "mock_fixture"),
    [
        ("sensor.washer_state", "mock_washer_api"),
        ("sensor.dryer_state", "mock_dryer_api"),
    ],
)
@pytest.mark.parametrize(
    ("machine_state", "expected_state"),
    [
        (MachineState.Standby, "standby"),
        (MachineState.Setting, "setting"),
        (MachineState.DelayCountdownMode, "delay_countdown"),
        (MachineState.DelayPause, "delay_paused"),
        (MachineState.SmartDelay, "smart_delay"),
        (MachineState.SmartGridPause, "smart_grid_pause"),
        (MachineState.Pause, "pause"),
        (MachineState.RunningMainCycle, "running_maincycle"),
        (MachineState.RunningPostCycle, "running_postcycle"),
        (MachineState.Exceptions, "exception"),
        (MachineState.Complete, "complete"),
        (MachineState.PowerFailure, "power_failure"),
        (MachineState.ServiceDiagnostic, "service_diagnostic_mode"),
        (MachineState.FactoryDiagnostic, "factory_diagnostic_mode"),
        (MachineState.LifeTest, "life_test"),
        (MachineState.CustomerFocusMode, "customer_focus_mode"),
        (MachineState.DemoMode, "demo_mode"),
        (MachineState.HardStopOrError, "hard_stop_or_error"),
        (MachineState.SystemInit, "system_initialize"),
    ],
)
async def test_washer_dryer_machine_states(
    hass: HomeAssistant,
    entity_id: str,
    mock_fixture: str,
    machine_state: MachineState,
    expected_state: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test Washer/Dryer machine states."""
    mock_instance = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    mock_instance.get_machine_state.return_value = machine_state
    await trigger_attr_callback(hass, mock_instance)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("entity_id", "mock_fixture"),
    [
        ("sensor.washer_state", "mock_washer_api"),
        ("sensor.dryer_state", "mock_dryer_api"),
    ],
)
@pytest.mark.parametrize(
    (
        "filling",
        "rinsing",
        "sensing",
        "soaking",
        "spinning",
        "washing",
        "expected_state",
    ),
    [
        (True, False, False, False, False, False, "cycle_filling"),
        (False, True, False, False, False, False, "cycle_rinsing"),
        (False, False, True, False, False, False, "cycle_sensing"),
        (False, False, False, True, False, False, "cycle_soaking"),
        (False, False, False, False, True, False, "cycle_spinning"),
        (False, False, False, False, False, True, "cycle_washing"),
    ],
)
async def test_washer_dryer_running_states(
    hass: HomeAssistant,
    entity_id: str,
    mock_fixture: str,
    filling: bool,
    rinsing: bool,
    sensing: bool,
    soaking: bool,
    spinning: bool,
    washing: bool,
    expected_state: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test Washer/Dryer machine states for RunningMainCycle."""
    mock_instance = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    mock_instance.get_machine_state.return_value = MachineState.RunningMainCycle
    mock_instance.get_cycle_status_filling.return_value = filling
    mock_instance.get_cycle_status_rinsing.return_value = rinsing
    mock_instance.get_cycle_status_sensing.return_value = sensing
    mock_instance.get_cycle_status_soaking.return_value = soaking
    mock_instance.get_cycle_status_spinning.return_value = spinning
    mock_instance.get_cycle_status_washing.return_value = washing

    await trigger_attr_callback(hass, mock_instance)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("entity_id", "mock_fixture"),
    [
        ("sensor.washer_state", "mock_washer_api"),
        ("sensor.dryer_state", "mock_dryer_api"),
    ],
)
async def test_washer_dryer_door_open_state(
    hass: HomeAssistant,
    entity_id: str,
    mock_fixture: str,
    request: pytest.FixtureRequest,
) -> None:
    """Test Washer/Dryer machine state when door is open."""
    mock_instance = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state.state == "running_maincycle"

    mock_instance.get_door_open.return_value = True

    await trigger_attr_callback(hass, mock_instance)
    state = hass.states.get(entity_id)
    assert state.state == "door_open"

    mock_instance.get_door_open.return_value = False

    await trigger_attr_callback(hass, mock_instance)
    state = hass.states.get(entity_id)
    assert state.state == "running_maincycle"


@pytest.mark.parametrize(
    ("entity_id", "mock_fixture", "mock_method_name", "values"),
    [
        (
            "sensor.washer_detergent_level",
            "mock_washer_api",
            "get_dispense_1_level",
            [
                (0, STATE_UNKNOWN),
                (1, "empty"),
                (2, "25"),
                (3, "50"),
                (4, "100"),
                (5, "active"),
            ],
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_simple_enum_sensors(
    hass: HomeAssistant,
    entity_id: str,
    mock_fixture: str,
    mock_method_name: str,
    values: list[tuple[int, str]],
    request: pytest.FixtureRequest,
) -> None:
    """Test simple enum sensors where state maps directly from a single API value."""
    await init_integration(hass)

    mock_instance = request.getfixturevalue(mock_fixture)
    mock_method = getattr(mock_instance, mock_method_name)
    for raw_value, expected_state in values:
        mock_method.return_value = raw_value

        await trigger_attr_callback(hass, mock_instance)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state
