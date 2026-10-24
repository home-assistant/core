"""Tests for the Overkiz climate platform."""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import OverkizState
from pyoverkiz.models import Event
import pytest
from pytest_homeassistant.common import snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DATA_COMPONENT as CLIMATE_DATA_COMPONENT,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.overkiz.climate.atlantic_pass_apc_zone_control_zone import (
    AtlanticPassAPCZoneControlZone,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.state import async_reproduce_state

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    assert_command_call,
    assert_commands_call,
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
# io:AtlanticHeatRecoveryVentilationIOComponent without io:VentilationModeState value
HEAT_RECOVERY_VENTILATION = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe.json",
    "io://1234-5678-6508/2840629#1",
    "climate.ventilation",
)

# io:AtlanticPassAPCZoneControlZoneComponent
ZONE_CONTROL_ZONE = FixtureDevice(
    "setup/cloud_atlantic_cozytouch_zone_control.json",
    "io://1234-1234-5752/960379#2",
    "climate.my_home_zone_control_living_room",
)

SNAPSHOT_FIXTURES = [
    VALVE,
    COZYTOUCH,
    YUTAKI_ZONE_1,
    THERMOSTAT_HEATING,
    HEAT_RECOVERY_VENTILATION,
    ZONE_CONTROL_ZONE,
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


# io:AtlanticPassAPCZoneControlMainComponent driving the operating mode of the zones
ZONE_CONTROL_MAIN_DEVICE_URL = "io://1234-1234-5752/960379#1"


async def _async_set_zone_control_operating_mode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    operating_mode: str,
    last_operating_mode: str = "heating",
) -> None:
    """Run the zone control in a mode, with heating and cooling on for the zone."""
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ZONE_CONTROL_MAIN_DEVICE_URL,
                device_states=[
                    {
                        "name": OverkizState.IO_PASS_APC_OPERATING_MODE,
                        "type": 3,
                        "value": operating_mode,
                    },
                    {
                        "name": OverkizState.IO_LAST_PASS_APC_OPERATING_MODE,
                        "type": 3,
                        "value": last_operating_mode,
                    },
                ],
            ),
            device_state_changed_event(
                device_url=ZONE_CONTROL_ZONE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_HEATING_ON_OFF,
                        "type": 3,
                        "value": "on",
                    },
                    {
                        "name": OverkizState.CORE_COOLING_ON_OFF,
                        "type": 3,
                        "value": "on",
                    },
                ],
            ),
        ],
    )


@pytest.mark.parametrize(
    (
        "operating_mode",
        "last_operating_mode",
        "temperature",
        "target_temp_low",
        "target_temp_high",
        "min_temp",
        "max_temp",
    ),
    [
        pytest.param("heating", "heating", 18.0, 18.0, 19.5, 16.5, 23.0, id="heating"),
        pytest.param("cooling", "cooling", 23.0, 25.0, 30.0, 19.0, 30.0, id="cooling"),
        pytest.param(
            "stop", "cooling", 23.0, 25.0, 30.0, 19.0, 30.0, id="stop_last_cooling"
        ),
        pytest.param(
            "drying", "heating", 18.0, 18.0, 19.5, 16.5, 23.0, id="drying_last_heating"
        ),
        # No side known: the heating and cooling setpoints
        pytest.param("stop", "stop", None, 18.0, 23.0, 16.5, 30.0, id="stop"),
    ],
)
async def test_zone_control_zone_active_side_setpoint(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    operating_mode: str,
    last_operating_mode: str,
    temperature: float | None,
    target_temp_low: float | None,
    target_temp_high: float | None,
    min_temp: float,
    max_temp: float,
) -> None:
    """Test a manual zone only exposes the setpoint of the active side."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(
        hass, freezer, mock_client, operating_mode, last_operating_mode
    )

    state = hass.states.get(ZONE_CONTROL_ZONE.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == target_temp_low
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == target_temp_high
    assert state.attributes[ATTR_MIN_TEMP] == min_temp
    assert state.attributes[ATTR_MAX_TEMP] == max_temp


@pytest.mark.parametrize(
    ("operating_mode", "command_name"),
    [
        pytest.param("heating", "setHeatingTargetTemperature", id="heating"),
        pytest.param("cooling", "setCoolingTargetTemperature", id="cooling"),
    ],
)
async def test_zone_control_zone_set_active_side_temperature(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    operating_mode: str,
    command_name: str,
) -> None:
    """Test a single setpoint is sent to the side the zone control is running."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(
        hass, freezer, mock_client, operating_mode
    )
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ZONE_CONTROL_ZONE.entity_id, ATTR_TEMPERATURE: 20.0},
        blocking=True,
    )

    commands = [
        (command.name, command.parameters)
        for call in mock_client.execute_action_group.await_args_list
        for action in call.kwargs["actions"]
        for command in action.commands
    ]
    assert commands[:2] == [
        (command_name, [20.0]),
        ("setDerogationOnOffState", ["on"]),
    ]


async def _async_set_zone_program(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    mode: str,
    derogation: str,
) -> None:
    """Set the mode of both sides of the zone and its derogation."""
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ZONE_CONTROL_ZONE.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_PASS_APC_HEATING_MODE,
                        "type": 3,
                        "value": mode,
                    },
                    {
                        "name": OverkizState.IO_PASS_APC_COOLING_MODE,
                        "type": 3,
                        "value": mode,
                    },
                    {
                        "name": OverkizState.CORE_DEROGATION_ON_OFF,
                        "type": 3,
                        "value": derogation,
                    },
                ],
            )
        ],
    )


@pytest.mark.parametrize(
    (
        "operating_mode",
        "derogation",
        "temperature",
        "target_temp_low",
        "target_temp_high",
    ),
    [
        # Eco then comfort heating setpoints
        pytest.param("heating", "off", None, 18.0, 19.5, id="heating"),
        # Comfort then eco cooling setpoints
        pytest.param("cooling", "off", None, 25.0, 30.0, id="cooling"),
        # The setpoint the zone applies during a derogation, and the program
        pytest.param("heating", "on", 8.0, 18.0, 19.5, id="heating_derogation"),
        pytest.param("cooling", "on", 8.0, 25.0, 30.0, id="cooling_derogation"),
    ],
)
async def test_zone_control_zone_program_setpoints(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    operating_mode: str,
    derogation: str,
    temperature: float | None,
    target_temp_low: float | None,
    target_temp_high: float | None,
) -> None:
    """Test a scheduled zone exposes the eco and comfort setpoints of its program."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(
        hass, freezer, mock_client, operating_mode
    )
    await _async_set_zone_program(
        hass, freezer, mock_client, "internalScheduling", derogation
    )

    state = hass.states.get(ZONE_CONTROL_ZONE.entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes.get(ATTR_TEMPERATURE) == temperature
    assert state.attributes.get(ATTR_TARGET_TEMP_LOW) == target_temp_low
    assert state.attributes.get(ATTR_TARGET_TEMP_HIGH) == target_temp_high


@pytest.mark.parametrize(
    ("operating_mode", "commands", "manual_command"),
    [
        pytest.param(
            "heating",
            [
                ("setEcoHeatingTargetTemperature", [19.0]),
                ("setComfortHeatingTargetTemperature", [21.0]),
            ],
            "setHeatingTargetTemperature",
            id="heating",
        ),
        pytest.param(
            "cooling",
            [
                ("setComfortCoolingTargetTemperature", [19.0]),
                ("setEcoCoolingTargetTemperature", [21.0]),
            ],
            "setCoolingTargetTemperature",
            id="cooling",
        ),
    ],
)
async def test_zone_control_zone_set_program_setpoints(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    operating_mode: str,
    commands: list[tuple[str, list[Any]]],
    manual_command: str,
) -> None:
    """Test a scheduled zone changes its setpoints without a derogation."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(
        hass, freezer, mock_client, operating_mode
    )
    await _async_set_zone_program(
        hass, freezer, mock_client, "internalScheduling", "off"
    )
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            "entity_id": ZONE_CONTROL_ZONE.entity_id,
            ATTR_TARGET_TEMP_LOW: 19.0,
            ATTR_TARGET_TEMP_HIGH: 21.0,
        },
        blocking=True,
    )

    # Only the setpoints written and the applied one are refreshed.
    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[
            *commands,
            *((name.replace("set", "refresh", 1), []) for name, _ in commands),
            ("refreshTargetTemperature", []),
        ],
    )

    # A single setpoint is kept as the manual one, it doesn't start a derogation
    # and there is nothing to refresh.
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ZONE_CONTROL_ZONE.entity_id, ATTR_TEMPERATURE: 20.0},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[(manual_command, [20.0])],
    )


async def test_zone_control_zone_set_derogation_setpoint(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a derogation started outside Home Assistant can be adjusted.

    The derogation is already on: only the setpoint is sent, and the applied
    setpoint it changes is refreshed, so that each step of a slider stays quick.
    """
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "cooling")
    await _async_set_zone_program(
        hass, freezer, mock_client, "internalScheduling", "on"
    )
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ZONE_CONTROL_ZONE.entity_id, ATTR_TEMPERATURE: 24.0},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[
            ("setCoolingTargetTemperature", [24.0]),
            ("refreshTargetTemperature", []),
        ],
    )


async def test_zone_control_zone_manual_step_sends_the_setpoint_only(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a step of a manual zone with its derogation on sends the setpoint only."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "heating")
    await _async_set_zone_program(hass, freezer, mock_client, "manu", "on")
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ZONE_CONTROL_ZONE.entity_id, ATTR_TEMPERATURE: 21.0},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[("setHeatingTargetTemperature", [21.0])],
    )


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
    (
        "mode",
        "heating_profile",
        "cooling_profile",
        "derogation",
        "target_temp_low",
        "target_temp_high",
    ),
    [
        pytest.param("manu", "manu", "manu", "off", 21.0, 26.0, id="manual"),
        pytest.param(
            "internalScheduling", "eco", "eco", "off", 18.0, 30.0, id="schedule_eco"
        ),
        pytest.param(
            "internalScheduling",
            "comfort",
            "comfort",
            "off",
            19.5,
            25.0,
            id="schedule_comfort",
        ),
        pytest.param(
            "internalScheduling",
            "comfort",
            "eco",
            "off",
            19.5,
            30.0,
            id="schedule_mixed_profiles",
        ),
        pytest.param(
            "internalScheduling",
            "derogation",
            "derogation",
            "on",
            21.0,
            26.0,
            id="schedule_derogation_profile",
        ),
        pytest.param(
            "internalScheduling",
            "eco",
            "eco",
            "on",
            21.0,
            26.0,
            id="schedule_derogation_state",
        ),
        pytest.param(
            "internalScheduling", "stop", "stop", "off", 21.0, 26.0, id="schedule_stop"
        ),
    ],
)
async def test_zone_control_zone_target_temperature_range(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    mode: str,
    heating_profile: str,
    cooling_profile: str,
    derogation: str,
    target_temp_low: float,
    target_temp_high: float,
) -> None:
    """Test the setpoint range follows the program profile when scheduled."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    # The range is only exposed while the zone control runs neither side.
    await _async_set_zone_control_operating_mode(
        hass, freezer, mock_client, "stop", "stop"
    )

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ZONE_CONTROL_ZONE.device_url,
                device_states=[
                    {
                        "name": OverkizState.IO_PASS_APC_HEATING_MODE,
                        "type": 3,
                        "value": mode,
                    },
                    {
                        "name": OverkizState.IO_PASS_APC_COOLING_MODE,
                        "type": 3,
                        "value": mode,
                    },
                    {
                        "name": OverkizState.IO_PASS_APC_HEATING_PROFILE,
                        "type": 3,
                        "value": heating_profile,
                    },
                    {
                        "name": OverkizState.IO_PASS_APC_COOLING_PROFILE,
                        "type": 3,
                        "value": cooling_profile,
                    },
                    {
                        "name": OverkizState.CORE_DEROGATION_ON_OFF,
                        "type": 3,
                        "value": derogation,
                    },
                    # Manual setpoints distinct from every program setpoint
                    {
                        "name": OverkizState.CORE_HEATING_TARGET_TEMPERATURE,
                        "type": 2,
                        "value": 21.0,
                    },
                    {
                        "name": OverkizState.CORE_COOLING_TARGET_TEMPERATURE,
                        "type": 2,
                        "value": 26.0,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(ZONE_CONTROL_ZONE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == target_temp_low
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == target_temp_high


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


ZONE_CONTROL_ZONE_REFRESH_COMMANDS: list[tuple[str, list[Any]]] = [
    ("refreshPassAPCHeatingMode", []),
    ("refreshPassAPCHeatingProfile", []),
    ("refreshPassAPCCoolingMode", []),
    ("refreshPassAPCCoolingProfile", []),
    ("refreshTargetTemperature", []),
]


def _zone_entity(hass: HomeAssistant) -> AtlanticPassAPCZoneControlZone:
    """Return the climate entity of the zone set up in a test."""
    entity = hass.data[CLIMATE_DATA_COMPONENT].get_entity(ZONE_CONTROL_ZONE.entity_id)
    assert isinstance(entity, AtlanticPassAPCZoneControlZone)
    return entity


@pytest.mark.parametrize(
    ("device_hvac_mode", "command"),
    [
        (HVACMode.HEAT, "setHeatingTargetTemperature"),
        (HVACMode.COOL, "setCoolingTargetTemperature"),
    ],
)
async def test_zone_control_zone_with_a_single_side(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    device_hvac_mode: HVACMode,
    command: str,
) -> None:
    """Test a zone that only heats or only cools writes the setpoint of its side."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "heating")
    await _async_set_zone_program(hass, freezer, mock_client, "manu", "on")
    mock_client.execute_action_group.reset_mock()

    entity = _zone_entity(hass)
    entity.__dict__["device_hvac_mode"] = device_hvac_mode
    assert entity.active_hvac_mode == device_hvac_mode

    await entity.async_set_temperature(**{ATTR_TEMPERATURE: 21.0})

    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[(command, [21.0])],
    )


async def test_zone_control_zone_without_a_known_mode(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a zone without a known mode offers no target temperature."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)

    entity = _zone_entity(hass)
    entity.__dict__["device_hvac_mode"] = None

    assert entity.supported_features == entity._attr_supported_features


async def test_zone_control_zone_with_the_derogated_temperature_fallback(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a zone that behaves like a heating zone has no program setpoints."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    entity = _zone_entity(hass)

    with patch.object(
        AtlanticPassAPCZoneControlZone,
        "is_using_derogated_temperature_fallback",
        new_callable=PropertyMock,
        return_value=True,
    ):
        assert entity.active_hvac_mode == entity.device_hvac_mode
        assert entity.active_program_setpoints is None
        assert entity.program_setpoints is None
        assert entity.supported_features == entity._attr_supported_features


@pytest.mark.parametrize(
    ("service", "service_data", "commands"),
    [
        pytest.param(
            "set_preset_mode",
            {ATTR_PRESET_MODE: "schedule"},
            [
                ("setPassAPCHeatingMode", ["internalScheduling"]),
                ("setPassAPCCoolingMode", ["internalScheduling"]),
                ("setDerogationOnOffState", ["off"]),
            ],
            id="preset_mode",
        ),
        pytest.param(
            "turn_off",
            {},
            [
                ("setCoolingOnOffState", ["off"]),
                ("setHeatingOnOffState", ["off"]),
            ],
            id="hvac_mode",
        ),
    ],
)
async def test_zone_control_zone_batches_commands(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    service: str,
    service_data: dict[str, Any],
    commands: list[tuple[str, list[Any]]],
) -> None:
    """Test a zone sends its commands and its refreshes as a single execution."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    # The zone control runs neither side.
    await _async_set_zone_control_operating_mode(
        hass, freezer, mock_client, "stop", "stop"
    )

    # Heating on puts the heating and cooling zone in heat_cool.
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ZONE_CONTROL_ZONE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_HEATING_ON_OFF,
                        "type": 3,
                        "value": "on",
                    },
                ],
            )
        ],
    )
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        service,
        {"entity_id": ZONE_CONTROL_ZONE.entity_id, **service_data},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[*commands, *ZONE_CONTROL_ZONE_REFRESH_COMMANDS],
    )


@pytest.mark.parametrize(
    ("preset_mode", "commands"),
    [
        pytest.param(
            "schedule",
            [
                ("setPassAPCHeatingMode", ["internalScheduling"]),
                ("setPassAPCCoolingMode", ["internalScheduling"]),
                ("setDerogationOnOffState", ["off"]),
            ],
            id="schedule",
        ),
        pytest.param(
            "manual",
            [
                ("setPassAPCHeatingMode", ["manu"]),
                ("setPassAPCCoolingMode", ["manu"]),
            ],
            id="manual",
        ),
    ],
)
async def test_zone_control_zone_preset_mode_with_derogation(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    preset_mode: str,
    commands: list[tuple[str, list[Any]]],
) -> None:
    """Test resuming the time program also ends a running derogation."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ZONE_CONTROL_ZONE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_DEROGATION_ON_OFF,
                        "type": 3,
                        "value": "on",
                    },
                ],
            )
        ],
    )
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": ZONE_CONTROL_ZONE.entity_id, ATTR_PRESET_MODE: preset_mode},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[*commands, *ZONE_CONTROL_ZONE_REFRESH_COMMANDS],
    )


async def test_zone_control_zone_derogation_applied_setpoint(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a derogation shows the setpoint the zone applies, not the manual one."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "cooling")
    await _async_set_zone_program(
        hass, freezer, mock_client, "internalScheduling", "on"
    )
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ZONE_CONTROL_ZONE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_COOLING_TARGET_TEMPERATURE,
                        "type": 2,
                        "value": 24.0,
                    },
                    {
                        "name": OverkizState.CORE_TARGET_TEMPERATURE,
                        "type": 2,
                        "value": 30.0,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(ZONE_CONTROL_ZONE.entity_id)
    assert state is not None
    assert state.attributes.get(ATTR_TEMPERATURE) == 30.0


async def test_zone_control_zone_set_temperature_while_off(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the setpoint of the running side is written while the zone is off."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "cooling")
    await _async_set_zone_program(hass, freezer, mock_client, "manu", "off")
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ZONE_CONTROL_ZONE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_HEATING_ON_OFF,
                        "type": 3,
                        "value": "off",
                    },
                    {
                        "name": OverkizState.CORE_COOLING_ON_OFF,
                        "type": 3,
                        "value": "off",
                    },
                ],
            )
        ],
    )
    state = hass.states.get(ZONE_CONTROL_ZONE.entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ZONE_CONTROL_ZONE.entity_id, ATTR_TEMPERATURE: 24.0},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[
            ("setCoolingTargetTemperature", [24.0]),
            ("setDerogationOnOffState", ["on"]),
            *ZONE_CONTROL_ZONE_REFRESH_COMMANDS,
        ],
    )


@pytest.mark.parametrize("program", ["internalScheduling", "manu"])
async def test_zone_control_zone_set_temperature_without_running_side(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    program: str,
) -> None:
    """Test a zone is not overridden when no side is running, in any mode."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(
        hass, freezer, mock_client, "stop", "stop"
    )
    await _async_set_zone_program(hass, freezer, mock_client, program, "off")
    mock_client.execute_action_group.reset_mock()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {
                "entity_id": ZONE_CONTROL_ZONE.entity_id,
                ATTR_TARGET_TEMP_LOW: 19.0,
                ATTR_TARGET_TEMP_HIGH: 24.0,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "zone_control_side_unknown"
    mock_client.execute_action_group.assert_not_called()


@pytest.mark.parametrize(
    (
        "saved_program",
        "saved_derogation",
        "saved_preset",
        "saved_attributes",
        "current_program",
        "commands",
    ),
    [
        pytest.param(
            "manu",
            "off",
            "manual",
            {ATTR_TEMPERATURE: 21.0},
            "internalScheduling",
            [
                [
                    ("setCoolingOnOffState", ["on"]),
                    ("setHeatingOnOffState", ["on"]),
                ],
                # Kept as the manual setpoint while scheduled
                [("setHeatingTargetTemperature", [21.0])],
                [
                    ("setPassAPCHeatingMode", ["manu"]),
                    ("setPassAPCCoolingMode", ["manu"]),
                ],
            ],
            id="manual_scene_while_scheduled",
        ),
        pytest.param(
            "internalScheduling",
            "off",
            "schedule",
            {ATTR_TARGET_TEMP_LOW: 19.0, ATTR_TARGET_TEMP_HIGH: 21.0},
            "manu",
            [
                [
                    ("setCoolingOnOffState", ["on"]),
                    ("setHeatingOnOffState", ["on"]),
                ],
                # The range is the program, even while the zone is manual
                [
                    ("setEcoHeatingTargetTemperature", [19.0]),
                    ("setComfortHeatingTargetTemperature", [21.0]),
                ],
                [
                    ("setPassAPCHeatingMode", ["internalScheduling"]),
                    ("setPassAPCCoolingMode", ["internalScheduling"]),
                    ("setDerogationOnOffState", ["off"]),
                ],
            ],
            id="scheduled_scene_while_manual",
        ),
    ],
)
async def test_zone_control_zone_restore_scene(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
    saved_program: str,
    saved_derogation: str,
    saved_preset: str,
    saved_attributes: dict[str, float],
    current_program: str,
    commands: list[list[tuple[str, list[Any]]]],
) -> None:
    """Test a scene saved in one mode is restored while the zone is in the other."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "heating")
    await _async_set_zone_program(hass, freezer, mock_client, current_program, "off")
    mock_client.execute_action_group.reset_mock()

    await async_reproduce_state(
        hass,
        [
            State(
                ZONE_CONTROL_ZONE.entity_id,
                HVACMode.HEAT_COOL,
                {ATTR_PRESET_MODE: saved_preset, **saved_attributes},
            )
        ],
    )

    sent = [
        [
            (command.name, command.parameters)
            for command in call.kwargs["actions"][0].commands
            if not command.name.startswith("refresh")
        ]
        for call in mock_client.execute_action_group.await_args_list
    ]
    assert sent == commands


async def test_zone_control_zone_range_while_manual(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a manual zone exposes the manual setpoint and the program range."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "heating")
    await _async_set_zone_program(hass, freezer, mock_client, "manu", "off")

    state = hass.states.get(ZONE_CONTROL_ZONE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    ) == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    assert state.attributes[ATTR_TEMPERATURE] == 18.0
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 18.0
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 19.5


async def test_zone_control_zone_manual_derogation_shows_manual_setpoint(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a manual zone shows its manual setpoint as soon as it is set.

    The applied setpoint is only refreshed later, and showing it would make the
    slider fall back to the previous value right after a change.
    """
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "heating")
    await _async_set_zone_program(hass, freezer, mock_client, "manu", "on")
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=ZONE_CONTROL_ZONE.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_HEATING_TARGET_TEMPERATURE,
                        "type": 2,
                        "value": 18.5,
                    },
                    {
                        "name": OverkizState.CORE_TARGET_TEMPERATURE,
                        "type": 2,
                        "value": 18.0,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(ZONE_CONTROL_ZONE.entity_id)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 18.5


async def test_zone_control_zone_single_setpoint_needs_a_known_side(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test a single setpoint is not offered while no side is heating or cooling."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(
        hass, freezer, mock_client, "stop", "stop"
    )
    await _async_set_zone_program(hass, freezer, mock_client, "manu", "off")
    mock_client.execute_action_group.reset_mock()

    state = hass.states.get(ZONE_CONTROL_ZONE.entity_id)
    assert state is not None
    features = ClimateEntityFeature(state.attributes[ATTR_SUPPORTED_FEATURES])
    assert ClimateEntityFeature.TARGET_TEMPERATURE_RANGE in features
    assert ClimateEntityFeature.TARGET_TEMPERATURE not in features

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {ATTR_ENTITY_ID: ZONE_CONTROL_ZONE.entity_id, ATTR_TEMPERATURE: 21.0},
            blocking=True,
        )

    mock_client.execute_action_group.assert_not_called()


async def test_zone_control_zone_saved_state_restores_range_and_setpoint(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test the range and the single setpoint of a saved state are both restored."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "heating")
    await _async_set_zone_program(hass, freezer, mock_client, "manu", "off")
    mock_client.execute_action_group.reset_mock()

    # What `climate.reproduce_state` sends for the attributes of a manual zone.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {
            ATTR_ENTITY_ID: ZONE_CONTROL_ZONE.entity_id,
            ATTR_TEMPERATURE: 21.0,
            ATTR_TARGET_TEMP_LOW: 18.5,
            ATTR_TARGET_TEMP_HIGH: 19.5,
        },
        blocking=True,
    )

    assert [
        [
            (str(command.name), command.parameters)
            for command in call.kwargs["actions"][0].commands
        ]
        for call in mock_client.execute_action_group.await_args_list
    ] == [
        [
            ("setEcoHeatingTargetTemperature", [18.5]),
            ("setComfortHeatingTargetTemperature", [19.5]),
            ("refreshEcoHeatingTargetTemperature", None),
            ("refreshComfortHeatingTargetTemperature", None),
            ("refreshTargetTemperature", None),
        ],
        [
            ("setHeatingTargetTemperature", [21.0]),
            ("setDerogationOnOffState", ["on"]),
            *((name, None) for name, _ in ZONE_CONTROL_ZONE_REFRESH_COMMANDS),
        ],
    ]


async def test_zone_control_zone_schedule_ends_a_derogation_not_reported_yet(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """Test resuming the schedule right after a temperature change ends the override."""
    await setup_overkiz_integration(fixture=ZONE_CONTROL_ZONE.fixture)
    await _async_set_zone_control_operating_mode(hass, freezer, mock_client, "heating")
    await _async_set_zone_program(hass, freezer, mock_client, "manu", "off")
    mock_client.execute_action_group.reset_mock()

    # The derogation is started, and the state does not report it yet.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: ZONE_CONTROL_ZONE.entity_id, ATTR_TEMPERATURE: 21.0},
        blocking=True,
    )
    mock_client.execute_action_group.reset_mock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {ATTR_ENTITY_ID: ZONE_CONTROL_ZONE.entity_id, ATTR_PRESET_MODE: "schedule"},
        blocking=True,
    )

    assert_commands_call(
        mock_client,
        device_url=ZONE_CONTROL_ZONE.device_url,
        commands=[
            ("setPassAPCHeatingMode", ["internalScheduling"]),
            ("setPassAPCCoolingMode", ["internalScheduling"]),
            ("setDerogationOnOffState", ["off"]),
            *ZONE_CONTROL_ZONE_REFRESH_COMMANDS,
        ],
    )
