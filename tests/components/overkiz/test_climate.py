"""Tests for the Overkiz climate platform."""

from collections.abc import Generator
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import OverkizState
from pyoverkiz.exceptions import OverkizError
from pyoverkiz.models import Event
import pytest
from pytest_homeassistant.common import (
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, restore_state as rs
from homeassistant.util import dt as dt_util

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    assert_command_call,
    async_deliver_events,
    device_available_event,
    device_removed_event,
    device_state_changed_event,
    device_unavailable_event,
)

# io:HeatingValveIOComponent
VALVE = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/15702199#1",
    "climate.maple_residence_garden_radiator",
)
# modbuslink:AtlanticElectricalHeaterWithAdjustableTemperatureSetpointMBLComponent
COZYTOUCH = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "modbuslink://1234-5678-5643/1#1",
    "climate.living_room_heater",
)
# Atlantic Calissia (io:AtlanticElectricalHeaterWithAdjustableTemperatureSetpointIOComponent)
ELECTRICAL_HEATER_ADJUSTABLE = FixtureDevice(
    "setup/cloud_atlantic_cozytouch.json",
    "io://1234-5678-5643/11009627#1",
    "climate.my_home_living_room_heater",
)

# Hitachi Yutaki 2-zone air-to-water heat pump
YUTAKI_ZONE_1 = FixtureDevice(
    "setup/cloud_hi_kumo_europe.json",
    "modbus://1234-5678-2284/5416194/1#2",
    "climate.somfy_tahoma_switch_yutaki_zone_1",
)
YUTAKI_ZONE_2 = FixtureDevice(
    "setup/cloud_hi_kumo_europe.json",
    "modbus://1234-5678-2284/5416194/1#3",
    "climate.somfy_tahoma_switch_yutaki_zone_2",
)
# io:HeatingThermostatIOComponent
THERMOSTAT_HEATING = FixtureDevice(
    "setup/cloud_somfy_tahoma_switch_sc_europe.json",
    "io://1234-5678-5010/386310#1",
    "climate.study_thermostat",
)
# Atlantic Adélis 2 Digit, without the towel dryer commands
TOWEL_DRYER_HEATING_LEVEL = FixtureDevice(
    "setup/cloud_atlantic_adelis_2_digit.json",
    "io://1234-5678-7259/9876543#1",
    "climate.bathroom_towel_dryer",
)
# io:AtlanticHeatRecoveryVentilationIOComponent without io:VentilationModeState value
HEAT_RECOVERY_VENTILATION = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe.json",
    "io://1234-5678-6508/2840629#1",
    "climate.ventilation",
)

SNAPSHOT_FIXTURES = [
    VALVE,
    COZYTOUCH,
    YUTAKI_ZONE_1,
    THERMOSTAT_HEATING,
    HEAT_RECOVERY_VENTILATION,
    TOWEL_DRYER_HEATING_LEVEL,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to climate only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_climate_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_valve_hvac_action_none_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test that hvac_action handles None valve state without crashing."""
    await setup_overkiz_integration(fixture=VALVE.fixture)

    state = hass.states.get(VALVE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.IDLE

    # Deliver an event that clears the valve state
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=VALVE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_OPEN_CLOSED_VALVE,
                        "type": 3,
                        "value": None,
                    }
                ],
            )
        ],
    )

    # hvac_action should be None (unknown) rather than raising KeyError
    state = hass.states.get(VALVE.entity_id)
    assert state is not None
    assert state.attributes.get(ATTR_HVAC_ACTION) is None


UNKNOWN_DEVICE_URL = "zigbee://1234-5678-1698/65535"


@pytest.mark.parametrize(
    "event",
    [
        pytest.param(device_available_event(UNKNOWN_DEVICE_URL), id="available"),
        pytest.param(device_unavailable_event(UNKNOWN_DEVICE_URL), id="unavailable"),
        pytest.param(
            device_state_changed_event(
                UNKNOWN_DEVICE_URL,
                [{"name": "core:OnOffState", "type": 3, "value": "on"}],
            ),
            id="state_changed",
        ),
        pytest.param(device_removed_event(UNKNOWN_DEVICE_URL), id="removed"),
    ],
)
async def test_events_for_unknown_device_url(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    event: Event,
) -> None:
    """Test that events for unknown device URLs don't crash the coordinator."""
    await setup_overkiz_integration(fixture=VALVE.fixture)

    await async_deliver_events(hass, freezer, mock_client, [event])

    # Should not crash; valve entity should still be available
    state = hass.states.get(VALVE.entity_id)
    assert state is not None


async def test_electrical_heater_adjustable_target_temperature(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test target_temperature tracks the effective setpoint only in auto mode."""
    await setup_overkiz_integration(fixture=ELECTRICAL_HEATER_ADJUSTABLE.fixture)

    # Fixture starts in auto (external) mode with the eco preset active.
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 16.5

    # The preset changes to comfort while still scheduled (auto).
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_TARGET_HEATING_LEVEL,
                        "type": 3,
                        "value": "comfort",
                    },
                    {
                        "name": OverkizState.IO_EFFECTIVE_TEMPERATURE_SETPOINT,
                        "type": 2,
                        "value": 20.0,
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 20.0

    # While scheduled (auto), setting a temperature derogates the active
    # preset instead of overwriting the comfort setpoint.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ELECTRICAL_HEATER_ADJUSTABLE.entity_id, ATTR_TEMPERATURE: 19.0},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
        command_name="setDerogatedTargetTemperature",
        parameters=[19.0],
    )

    # The device reports the derogation by updating the effective setpoint.
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_EFFECTIVE_TEMPERATURE_SETPOINT,
                        "type": 2,
                        "value": 19.0,
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 19.0

    mock_client.execute_action_group.reset_mock()

    # Leaving auto (scheduled) mode for manual falls back to
    # core:TargetTemperatureState, and setting a temperature now targets
    # that state directly instead of derogating.
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_OPERATING_MODE,
                        "type": 3,
                        "value": "manual",
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 20.0

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ELECTRICAL_HEATER_ADJUSTABLE.entity_id, ATTR_TEMPERATURE: 21.0},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
        command_name="setTargetTemperature",
        parameters=[21.0],
    )

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_TARGET_TEMPERATURE,
                        "type": 2,
                        "value": 21.0,
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 21.0


@pytest.mark.parametrize(
    ("device_states", "expected_hvac_action"),
    [
        pytest.param(
            [
                {
                    "name": OverkizState.IO_CURRENT_WORKING_RATE,
                    "type": 2,
                    "value": 51.0,
                },
                {
                    "name": OverkizState.CORE_REGULATION_MODE,
                    "type": 3,
                    "value": "standby",
                },
            ],
            HVACAction.HEATING,
            id="working_rate_heating",
        ),
        pytest.param(
            [
                {
                    "name": OverkizState.IO_CURRENT_WORKING_RATE,
                    "type": 2,
                    "value": 0.0,
                },
            ],
            HVACAction.IDLE,
            id="working_rate_idle",
        ),
        pytest.param(
            [
                {
                    "name": OverkizState.IO_CURRENT_WORKING_RATE,
                    "type": 2,
                    "value": 51.0,
                },
                {
                    "name": OverkizState.CORE_OPERATING_MODE,
                    "type": 3,
                    "value": "standby",
                },
            ],
            HVACAction.OFF,
            id="working_rate_hvac_mode_off",
        ),
        pytest.param(
            [
                {
                    "name": OverkizState.IO_CURRENT_WORKING_RATE,
                    "type": 0,
                    "value": None,
                },
                {
                    "name": OverkizState.CORE_REGULATION_MODE,
                    "type": 3,
                    "value": "increase",
                },
            ],
            HVACAction.HEATING,
            id="regulation_mode_fallback",
        ),
    ],
)
async def test_electrical_heater_adjustable_hvac_action(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    device_states: list[dict[str, Any]],
    expected_hvac_action: HVACAction,
) -> None:
    """Test hvac_action prefers the working rate over the regulation mode."""
    await setup_overkiz_integration(fixture=ELECTRICAL_HEATER_ADJUSTABLE.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ELECTRICAL_HEATER_ADJUSTABLE.device_url,
                device_states=device_states,
            )
        ],
    )

    state = hass.states.get(ELECTRICAL_HEATER_ADJUSTABLE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_HVAC_ACTION] == expected_hvac_action


async def test_hitachi_air_to_water_heating_zone_2(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the second heating zone reads its own Zone2 states."""
    await setup_overkiz_integration(fixture=YUTAKI_ZONE_2.fixture)

    zone_1 = hass.states.get(YUTAKI_ZONE_1.entity_id)
    assert zone_1 is not None
    assert zone_1.attributes[ATTR_CURRENT_TEMPERATURE] == 18.5

    zone_2 = hass.states.get(YUTAKI_ZONE_2.entity_id)
    assert zone_2 is not None
    assert zone_2.state == HVACMode.AUTO
    assert zone_2.attributes[ATTR_CURRENT_TEMPERATURE] == 20.5
    assert zone_2.attributes[ATTR_TEMPERATURE] == 21.0


async def test_thermostat_heating_set_temperature(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test setting a temperature issues setDerogation, not setComfortTemperature."""
    await setup_overkiz_integration(fixture=THERMOSTAT_HEATING.fixture)

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": THERMOSTAT_HEATING.entity_id, ATTR_TEMPERATURE: 20.0},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=THERMOSTAT_HEATING.device_url,
        command_name="setDerogation",
        parameters=[20.0, "further_notice"],
    )


@pytest.mark.parametrize(
    ("preset_mode", "parameters"),
    [
        pytest.param("away", ["away", "further_notice"], id="away"),
        pytest.param("comfort", ["comfort", "further_notice"], id="comfort"),
        pytest.param("eco", ["eco", "further_notice"], id="eco"),
        # Manual re-sends the current temperature to enter the derogation
        pytest.param("manual", [26.6, "further_notice"], id="manual"),
    ],
)
async def test_thermostat_heating_set_preset_mode(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    preset_mode: str,
    parameters: list[str | float],
) -> None:
    """Test selecting a preset issues setDerogation with the mapped parameter."""
    await setup_overkiz_integration(fixture=THERMOSTAT_HEATING.fixture)

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": THERMOSTAT_HEATING.entity_id, ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=THERMOSTAT_HEATING.device_url,
        command_name="setDerogation",
        parameters=parameters,
    )


@pytest.mark.parametrize(
    ("service", "service_data"),
    [
        pytest.param("set_fan_mode", {ATTR_FAN_MODE: "bypass_boost"}, id="fan_mode"),
        pytest.param("set_preset_mode", {ATTR_PRESET_MODE: "prog"}, id="preset_mode"),
    ],
)
async def test_heat_recovery_ventilation_without_ventilation_mode(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    service: str,
    service_data: dict[str, str],
) -> None:
    """Test setting modes does not fail without an io:VentilationModeState value."""
    await setup_overkiz_integration(fixture=HEAT_RECOVERY_VENTILATION.fixture)

    await hass.services.async_call(
        "climate",
        service,
        {"entity_id": HEAT_RECOVERY_VENTILATION.entity_id, **service_data},
        blocking=True,
    )


@pytest.fixture
def no_cancel_settle_delay() -> Generator[None]:
    """Skip the pause between a boost cancel and the next heating level."""
    with patch(
        "homeassistant.components.overkiz.climate."
        "atlantic_electrical_towel_dryer_heating_level.CANCEL_SETTLE_DELAY",
        0,
    ):
        yield


def sent_commands(mock_client: MockOverkizClient) -> list[tuple[str, list[Any]]]:
    """Return every command sent to the towel dryer, one per action group."""
    commands = []
    for call in mock_client.execute_action_group.await_args_list:
        (action,) = call.kwargs["actions"]
        assert action.device_url == TOWEL_DRYER_HEATING_LEVEL.device_url
        commands.extend(
            (command.name, command.parameters or []) for command in action.commands
        )
    return commands


@pytest.mark.parametrize(
    ("service", "service_data", "expected_level"),
    [
        pytest.param("set_hvac_mode", {"hvac_mode": HVACMode.OFF}, "off", id="off"),
        pytest.param(
            "set_hvac_mode", {"hvac_mode": HVACMode.HEAT}, "comfort", id="heat"
        ),
        pytest.param(
            "set_preset_mode", {ATTR_PRESET_MODE: "comfort-1"}, "comfort-1", id="c-1"
        ),
        pytest.param(
            "set_preset_mode",
            {ATTR_PRESET_MODE: "frost_protection"},
            "frostprotection",
            id="frost_protection",
        ),
    ],
)
async def test_towel_dryer_heating_level_set_level(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    service: str,
    service_data: dict[str, Any],
    expected_level: str,
) -> None:
    """Test heating levels are set directly when no boost is running."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)

    await hass.services.async_call(
        "climate",
        service,
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, **service_data},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
        command_name="setHeatingLevel",
        parameters=[expected_level],
    )


async def test_towel_dryer_heating_level_set_temperature(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test setting the target temperature."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
        command_name="setTargetTemperature",
        parameters=[22.0],
    )


@pytest.mark.usefixtures("freezer", "no_cancel_settle_delay")
async def test_towel_dryer_heating_level_boost(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a boost is timed, then cancelled before the next heating level."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
        command_name="setHeatingLevelWithTimer",
        parameters=["boost", 60],
    )
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "boost"
    # The boost and the level to return to are kept across a restart
    stored = {
        stored.state.entity_id: stored.extra_data
        for stored in rs.async_get(hass).async_get_stored_states()
    }
    extra_data = stored[TOWEL_DRYER_HEATING_LEVEL.entity_id]
    assert extra_data is not None
    assert extra_data.as_dict() == {
        "assumed_level": "eco",
        "boost_until": (dt_util.utcnow() + timedelta(minutes=60)).isoformat(),
        "override_pending": True,
        "boost_timer_seen": False,
    }

    mock_client.execute_action_group.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "eco"},
        blocking=True,
    )

    # The cancel and the new level are sent as separate executions
    assert sent_commands(mock_client) == [
        ("cancelHeatingLevel", ["boost"]),
        ("setHeatingLevel", ["eco"]),
    ]
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "eco"


async def test_towel_dryer_heating_level_boost_ends(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the level from before the boost is shown when the boost ends."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_TARGET_HEATING_LEVEL,
                        "type": 3,
                        "value": "comfort",
                    },
                    {
                        "name": OverkizState.IO_TIMER_FOR_TRANSITORY_STATE,
                        "type": 1,
                        "value": 60,
                    },
                ],
            )
        ],
    )
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "boost"

    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # The gateway still reports comfort, but the device is back on eco
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "eco"

    # A cancel resets the timer, the level stays stale until a new one is set
    for timer, expected_preset in ((0, "eco"), (65535, "comfort")):
        await async_deliver_events(
            hass,
            freezer,
            mock_client,
            [
                device_state_changed_event(
                    device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
                    device_states=[
                        {
                            "name": OverkizState.IO_TIMER_FOR_TRANSITORY_STATE,
                            "type": 1,
                            "value": timer,
                        }
                    ],
                )
            ],
        )
        state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
        assert state is not None
        assert state.attributes[ATTR_PRESET_MODE] == expected_preset


@pytest.mark.parametrize(
    "device_states",
    [
        pytest.param(
            [
                {
                    "name": OverkizState.IO_TIMER_FOR_TRANSITORY_STATE,
                    "type": 1,
                    "value": 60,
                }
            ],
            id="timer",
        ),
        pytest.param(
            [
                {
                    "name": OverkizState.IO_TARGET_HEATING_LEVEL,
                    "type": 3,
                    "value": "boost",
                }
            ],
            id="level",
        ),
    ],
)
@pytest.mark.usefixtures("no_cancel_settle_delay")
async def test_towel_dryer_heating_level_cancels_gateway_boost(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    device_states: list[dict[str, Any]],
) -> None:
    """Test a boost not started from Home Assistant is cancelled first."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
                device_states=device_states,
            )
        ],
    )

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )

    assert sent_commands(mock_client) == [
        ("cancelHeatingLevel", ["boost"]),
        ("setHeatingLevel", ["off"]),
    ]


@pytest.mark.parametrize(
    ("device_states", "expected_hvac_action"),
    [
        pytest.param(
            [
                {
                    "name": OverkizState.CORE_REGULATION_MODE,
                    "type": 3,
                    "value": "increase",
                }
            ],
            HVACAction.HEATING,
            id="heating",
        ),
        pytest.param(
            [
                {
                    "name": OverkizState.IO_TARGET_HEATING_LEVEL,
                    "type": 3,
                    "value": "off",
                },
                {
                    "name": OverkizState.CORE_REGULATION_MODE,
                    "type": 3,
                    "value": "increase",
                },
            ],
            HVACAction.OFF,
            id="off",
        ),
    ],
)
async def test_towel_dryer_heating_level_hvac_action(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    device_states: list[dict[str, Any]],
    expected_hvac_action: HVACAction,
) -> None:
    """Test hvac_action follows the regulation mode and the heating level."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
                device_states=device_states,
            )
        ],
    )

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_HVAC_ACTION] == expected_hvac_action


async def test_towel_dryer_heating_level_boost_not_from_home_assistant(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a boost level reported without a boost from Home Assistant is comfort."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_TARGET_HEATING_LEVEL,
                        "type": 3,
                        "value": "boost",
                    }
                ],
            )
        ],
    )

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "comfort"


async def test_towel_dryer_heating_level_restore_boost(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a boost running across a restart still ends on the previous level."""
    boost_until = dt_util.utcnow() + timedelta(minutes=30)
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(TOWEL_DRYER_HEATING_LEVEL.entity_id, "heat"),
                {
                    "assumed_level": "eco",
                    "boost_until": boost_until.isoformat(),
                    "override_pending": True,
                    "boost_timer_seen": False,
                },
            )
        ],
    )
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_TARGET_HEATING_LEVEL,
                        "type": 3,
                        "value": "comfort",
                    },
                    {
                        "name": OverkizState.IO_TIMER_FOR_TRANSITORY_STATE,
                        "type": 1,
                        "value": 60,
                    },
                ],
            )
        ],
    )
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "boost"

    freezer.tick(timedelta(minutes=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "eco"


async def test_towel_dryer_heating_level_restore_invalid_data(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test incomplete stored data is ignored."""
    mock_restore_cache_with_extra_data(
        hass,
        [(State(TOWEL_DRYER_HEATING_LEVEL.entity_id, "heat"), {"boost_until": None})],
    )
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "eco"


def towel_dryer_states_event(level: str, timer: int) -> Event:
    """Return a gateway event with the heating level and the transitory timer."""
    return device_state_changed_event(
        device_url=TOWEL_DRYER_HEATING_LEVEL.device_url,
        device_states=[
            {"name": OverkizState.IO_TARGET_HEATING_LEVEL, "type": 3, "value": level},
            {
                "name": OverkizState.IO_TIMER_FOR_TRANSITORY_STATE,
                "type": 1,
                "value": timer,
            },
        ],
    )


async def test_towel_dryer_heating_level_boost_cancelled_elsewhere(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a boost cancelled by another client is no longer shown."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("comfort", 60)]
    )
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "boost"

    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("off", 65535)]
    )

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("no_cancel_settle_delay")
async def test_towel_dryer_heating_level_cancel_after_boost_ran_out(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the boost is cancelled though the gateway never reported its timer."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_client.execute_action_group.reset_mock()
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "eco"},
        blocking=True,
    )

    assert sent_commands(mock_client) == [
        ("cancelHeatingLevel", ["boost"]),
        ("setHeatingLevel", ["eco"]),
    ]


@pytest.mark.usefixtures("no_cancel_settle_delay")
async def test_towel_dryer_heating_level_set_level_fails(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the boost is still tracked when the new level can't be sent."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )

    mock_client.execute_action_group.side_effect = OverkizError("Server error")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id,
                "hvac_mode": HVACMode.OFF,
            },
            blocking=True,
        )

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_PRESET_MODE] == "boost"


async def test_towel_dryer_heating_level_boost_after_pending_level(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a level not yet reported by the gateway is shown and returned to."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "comfort"},
        blocking=True,
    )
    # The gateway still reports eco
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("eco", 65535)]
    )
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "comfort"

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("eco", 60)]
    )
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "comfort"


async def test_towel_dryer_heating_level_confirmed_level(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the gateway level is followed once it confirms the level sent."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "comfort"},
        blocking=True,
    )
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("comfort", 65535)]
    )
    # A change made in another client
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("frostprotection", 65535)]
    )

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "frost_protection"


async def test_towel_dryer_heating_level_set_temperature_and_hvac_mode(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the hvac mode is applied before the target temperature."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id,
            ATTR_TEMPERATURE: 22.0,
            "hvac_mode": HVACMode.OFF,
        },
        blocking=True,
    )

    assert sent_commands(mock_client) == [
        ("setHeatingLevel", ["off"]),
        ("setTargetTemperature", [22.0]),
    ]


async def test_towel_dryer_heating_level_boost_cancelled_timer(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a stale timer is ignored and a cancelled boost ends on its level."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "comfort"},
        blocking=True,
    )
    # Left by a previous cancel, before the gateway reports the level set after it
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("eco", 0)]
    )
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("comfort", 65535)]
    )
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "boost"

    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("eco", 60)]
    )
    # Cancelled by another client
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("eco", 0)]
    )

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] == "comfort"


async def test_towel_dryer_heating_level_pending_level_expires(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the gateway level is followed when the level sent is never reported."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF

    freezer.tick(timedelta(minutes=3))
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("eco", 65535)]
    )

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_PRESET_MODE] == "eco"


async def test_towel_dryer_heating_level_boost_before_level_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a boost returns to a level sent but never reported by the gateway."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_towel_dryer_heating_level_boost_after_expired_level(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a boost returns to the gateway level once the level sent expired."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    # No update reaches the entity before the boost starts
    freezer.tick(timedelta(minutes=3))
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )
    await async_deliver_events(
        hass, freezer, mock_client, [towel_dryer_states_event("eco", 60)]
    )
    freezer.tick(timedelta(minutes=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_PRESET_MODE] == "eco"


@pytest.mark.usefixtures("no_cancel_settle_delay")
async def test_towel_dryer_heating_level_set_level_fails_after_cancel(
    hass: HomeAssistant,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the boost is no longer tracked once cancelled, even if the level fails."""
    await setup_overkiz_integration(fixture=TOWEL_DRYER_HEATING_LEVEL.fixture)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id, ATTR_PRESET_MODE: "boost"},
        blocking=True,
    )

    mock_client.execute_action_group.side_effect = [
        "exec-cancel",
        OverkizError("Server error"),
    ]
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": TOWEL_DRYER_HEATING_LEVEL.entity_id,
                "hvac_mode": HVACMode.OFF,
            },
            blocking=True,
        )

    state = hass.states.get(TOWEL_DRYER_HEATING_LEVEL.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_PRESET_MODE] == "eco"
