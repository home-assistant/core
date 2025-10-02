"""Test the Whirlpool Sensor domain."""

from datetime import UTC, datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from whirlpool.dryer import MachineState as DryerMachineState
from whirlpool.oven import CavityState as OvenCavityState, CookMode
from whirlpool.washer import MachineState as WasherMachineState

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
    mock_instance.get_machine_state.return_value = WasherMachineState.Pause
    await init_integration(hass)

    # Test restored state.
    state = hass.states.get(entity_id)
    assert state.state == restored_datetime.isoformat()

    # Test no time change because the machine is not running.
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    assert state.state == restored_datetime.isoformat()

    # Test new time when machine starts a cycle.
    if "washer" in entity_id:
        mock_instance.get_machine_state.return_value = (
            WasherMachineState.RunningMainCycle
        )
    else:
        mock_instance.get_machine_state.return_value = (
            DryerMachineState.RunningMainCycle
        )

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
    if "washer" in entity_id:
        mock_instance.get_machine_state.return_value = WasherMachineState.Pause
    else:
        mock_instance.get_machine_state.return_value = DryerMachineState.Pause
    await init_integration(hass)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN

    # Test no change because the machine is paused.
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN

    # Test new time when machine starts a cycle.
    if "washer" in entity_id:
        mock_instance.get_machine_state.return_value = (
            WasherMachineState.RunningMainCycle
        )
    else:
        mock_instance.get_machine_state.return_value = (
            DryerMachineState.RunningMainCycle
        )
    mock_instance.get_time_remaining.return_value = 60
    await trigger_attr_callback(hass, mock_instance)

    state = hass.states.get(entity_id)
    expected_time = (now + timedelta(seconds=60)).isoformat()
    assert state.state == expected_time


@pytest.mark.parametrize(
    ("machine_state", "expected_state"),
    [
        (WasherMachineState.Standby, "standby"),
        (WasherMachineState.Setting, "setting"),
        (WasherMachineState.DelayCountdownMode, "delay_countdown"),
        (WasherMachineState.DelayPause, "delay_paused"),
        (WasherMachineState.SmartDelay, "smart_delay"),
        (WasherMachineState.SmartGridPause, "smart_grid_pause"),
        (WasherMachineState.Pause, "pause"),
        (WasherMachineState.RunningMainCycle, "running_maincycle"),
        (WasherMachineState.RunningPostCycle, "running_postcycle"),
        (WasherMachineState.Exceptions, "exception"),
        (WasherMachineState.Complete, "complete"),
        (WasherMachineState.PowerFailure, "power_failure"),
        (WasherMachineState.ServiceDiagnostic, "service_diagnostic_mode"),
        (WasherMachineState.FactoryDiagnostic, "factory_diagnostic_mode"),
        (WasherMachineState.LifeTest, "life_test"),
        (WasherMachineState.CustomerFocusMode, "customer_focus_mode"),
        (WasherMachineState.DemoMode, "demo_mode"),
        (WasherMachineState.HardStopOrError, "hard_stop_or_error"),
        (WasherMachineState.SystemInit, "system_initialize"),
    ],
)
async def test_washer_machine_states(
    hass: HomeAssistant,
    machine_state: WasherMachineState,
    expected_state: str,
    mock_washer_api,
) -> None:
    """Test Washer machine states."""
    await init_integration(hass)

    mock_washer_api.get_machine_state.return_value = machine_state
    await trigger_attr_callback(hass, mock_washer_api)
    state = hass.states.get("sensor.washer_state")
    assert state is not None
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("machine_state", "expected_state"),
    [
        (DryerMachineState.Standby, "standby"),
        (DryerMachineState.Setting, "setting"),
        (DryerMachineState.DelayCountdownMode, "delay_countdown"),
        (DryerMachineState.DelayPause, "delay_paused"),
        (DryerMachineState.SmartDelay, "smart_delay"),
        (DryerMachineState.SmartGridPause, "smart_grid_pause"),
        (DryerMachineState.Pause, "pause"),
        (DryerMachineState.RunningMainCycle, "running_maincycle"),
        (DryerMachineState.RunningPostCycle, "running_postcycle"),
        (DryerMachineState.Exceptions, "exception"),
        (DryerMachineState.Complete, "complete"),
        (DryerMachineState.PowerFailure, "power_failure"),
        (DryerMachineState.ServiceDiagnostic, "service_diagnostic_mode"),
        (DryerMachineState.FactoryDiagnostic, "factory_diagnostic_mode"),
        (DryerMachineState.LifeTest, "life_test"),
        (DryerMachineState.CustomerFocusMode, "customer_focus_mode"),
        (DryerMachineState.DemoMode, "demo_mode"),
        (DryerMachineState.HardStopOrError, "hard_stop_or_error"),
        (DryerMachineState.SystemInit, "system_initialize"),
        (DryerMachineState.Cancelled, "cancelled"),
    ],
)
async def test_dryer_machine_states(
    hass: HomeAssistant,
    machine_state: DryerMachineState,
    expected_state: str,
    mock_dryer_api,
) -> None:
    """Test Dryer machine states."""
    await init_integration(hass)

    mock_dryer_api.get_machine_state.return_value = machine_state
    await trigger_attr_callback(hass, mock_dryer_api)
    state = hass.states.get("sensor.dryer_state")
    assert state is not None
    assert state.state == expected_state


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
async def test_washer_running_states(
    hass: HomeAssistant,
    filling: bool,
    rinsing: bool,
    sensing: bool,
    soaking: bool,
    spinning: bool,
    washing: bool,
    expected_state: str,
    mock_washer_api,
) -> None:
    """Test Washer machine states for RunningMainCycle."""
    await init_integration(hass)

    mock_washer_api.get_machine_state.return_value = WasherMachineState.RunningMainCycle
    mock_washer_api.get_cycle_status_filling.return_value = filling
    mock_washer_api.get_cycle_status_rinsing.return_value = rinsing
    mock_washer_api.get_cycle_status_sensing.return_value = sensing
    mock_washer_api.get_cycle_status_soaking.return_value = soaking
    mock_washer_api.get_cycle_status_spinning.return_value = spinning
    mock_washer_api.get_cycle_status_washing.return_value = washing

    await trigger_attr_callback(hass, mock_washer_api)
    state = hass.states.get("sensor.washer_state")
    assert state is not None
    assert state.state == expected_state


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
        (
            "sensor.oven_upper_oven_state",
            "mock_oven_api",
            "get_cavity_state",
            [
                (OvenCavityState.Standby, "standby"),
                (OvenCavityState.Preheating, "preheating"),
                (OvenCavityState.Cooking, "cooking"),
                (OvenCavityState.NotPresent, "not_present"),
                (None, STATE_UNKNOWN),
            ],
        ),
        (
            "sensor.oven_upper_oven_cook_mode",
            "mock_oven_api",
            "get_cook_mode",
            [
                (CookMode.Standby, "standby"),
                (CookMode.Bake, "bake"),
                (CookMode.ConvectBake, "convection_bake"),
                (CookMode.Broil, "broil"),
                (CookMode.ConvectBroil, "convection_broil"),
                (CookMode.ConvectRoast, "convection_roast"),
                (CookMode.KeepWarm, "keep_warm"),
                (CookMode.AirFry, "air_fry"),
                (None, STATE_UNKNOWN),
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
