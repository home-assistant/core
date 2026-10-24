"""Test the Mitsubishi WF-RAC climate platform."""

import asyncio
from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pywfrac import (
    AIRFLOW_UNKNOWN,
    AirconCommands,
    OperationMode,
    WfRacCommandError,
    WindDirectionLR,
    WindDirectionUD,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_SWING_HORIZONTAL_MODE,
    ATTR_SWING_HORIZONTAL_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.mitsubishi_wf_rac.const import (
    HOME_LEAVE_TEMP_COOL,
    HOME_LEAVE_TEMP_HEAT,
    SWING_3D_AUTO,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import advance_polls, model

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.living_room"
# Raw values that name no enum member.
OPERATION_MODE_UNKNOWN = 99
WIND_DIRECTION_UNKNOWN = 99

RUNNING_COOL = {"Operation": True, "OperationMode": OperationMode.COOL}
RUNNING_HEAT = {"Operation": True, "OperationMode": OperationMode.HEAT}
WIDE_RANGE_HEATING = {**model(3), **RUNNING_HEAT}


def _sent(mock_repository: MagicMock) -> dict[AirconCommands, Any]:
    """The parameters of the command the integration last sent."""
    return mock_repository.async_send_command.await_args.args[2]


async def _call(
    hass: HomeAssistant, service: str, data: dict[str, Any] | None = None
) -> None:
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **(data or {})},
        blocking=True,
    )


async def test_entity(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """The climate entity reflects the state the module reported."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_state_from_the_module(hass: HomeAssistant) -> None:
    """The captured frame has the unit off, in cool, set to 22 degrees."""
    state = hass.states.get(ENTITY_ID)

    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 22.0
    assert state.attributes["current_temperature"] == 24.7


@pytest.mark.parametrize(
    ("service", "data", "expected"),
    [
        pytest.param(
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            {
                AirconCommands.OperationMode: OperationMode.HEAT,
                AirconCommands.Operation: True,
            },
            id="hvac_mode",
        ),
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 21.0},
            {AirconCommands.PresetTemp: 21.0},
            id="temperature",
        ),
        pytest.param(
            SERVICE_SET_FAN_MODE,
            {ATTR_FAN_MODE: "high"},
            {AirconCommands.AirFlow: 4},
            id="fan",
        ),
        pytest.param(
            SERVICE_SET_SWING_MODE,
            {ATTR_SWING_MODE: "lowest"},
            {AirconCommands.WindDirectionUD: 4, AirconCommands.Entrust: False},
            id="vertical_swing",
        ),
        pytest.param(
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {ATTR_SWING_HORIZONTAL_MODE: "left_left"},
            {AirconCommands.WindDirectionLR: 1, AirconCommands.Entrust: False},
            id="horizontal_swing",
        ),
        pytest.param(
            SERVICE_SET_SWING_MODE,
            {ATTR_SWING_MODE: SWING_3D_AUTO},
            {AirconCommands.Entrust: True},
            id="3d_auto",
        ),
        pytest.param(SERVICE_TURN_ON, {}, {AirconCommands.Operation: True}, id="on"),
        pytest.param(SERVICE_TURN_OFF, {}, {AirconCommands.Operation: False}, id="off"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_commands_reach_the_module(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    service: str,
    data: dict[str, Any],
    expected: dict[AirconCommands, Any],
) -> None:
    """Every setter ends up as one command carrying what was asked for."""
    await _call(hass, service, data)

    mock_repository.async_send_command.assert_awaited_once()
    assert _sent(mock_repository) == expected


@pytest.mark.usefixtures("init_integration")
async def test_the_answer_to_a_command_reaches_the_state(
    hass: HomeAssistant,
) -> None:
    """The entity shows what the unit answered, not what it is waiting for."""
    await _call(hass, SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "high"})

    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODE] == "high"


@pytest.mark.parametrize(
    ("asked", "sent"),
    [
        pytest.param(21.4, 21.5, id="up to the nearer half"),
        pytest.param(21.2, 21.0, id="down to the nearer half"),
        pytest.param(21.5, 21.5, id="already on a half"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_a_setpoint_between_two_halves_is_rounded_not_truncated(
    hass: HomeAssistant, mock_repository: MagicMock, asked: float, sent: float
) -> None:
    """The frame truncates to half degrees, so the setpoint is rounded first."""
    await _call(hass, SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: asked})

    assert _sent(mock_repository)[AirconCommands.PresetTemp] == sent


@pytest.mark.usefixtures("init_integration")
async def test_temperature_outside_the_units_range_is_refused(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """Refuse a setpoint the unit itself does not offer, instead of clamping it."""
    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 40.0})

    mock_repository.async_send_command.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_without_a_single_setpoint(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """A target_temp_high/low pair is refused; the unit has one setpoint."""
    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            SERVICE_SET_TEMPERATURE,
            {"target_temp_low": 20.0, "target_temp_high": 24.0},
        )

    mock_repository.async_send_command.assert_not_awaited()


@pytest.mark.parametrize(
    ("aircon_fields", "away_temp"),
    [
        pytest.param(RUNNING_COOL, HOME_LEAVE_TEMP_COOL, id="cooling"),
        pytest.param(RUNNING_HEAT, HOME_LEAVE_TEMP_HEAT, id="heating"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_preset_away_switches_the_unit_to_home_leave(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    aircon_fields: dict[str, Any],
    away_temp: float,
) -> None:
    """The away preset writes the Home Leave target of the running direction."""
    await _call(hass, SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_AWAY})

    assert _sent(mock_repository) == {
        AirconCommands.Operation: True,
        AirconCommands.OperationMode: aircon_fields["OperationMode"],
        AirconCommands.PresetTemp: away_temp,
    }


@pytest.mark.usefixtures("init_integration")
async def test_the_advertised_range_covers_the_away_setpoints(
    hass: HomeAssistant,
) -> None:
    """The advertised range covers the Home Leave setpoints."""
    attributes = hass.states.get(ENTITY_ID).attributes

    assert attributes[ATTR_MIN_TEMP] <= HOME_LEAVE_TEMP_HEAT
    assert attributes[ATTR_MAX_TEMP] >= HOME_LEAVE_TEMP_COOL


@pytest.mark.parametrize("aircon_fields", [model(2)])
@pytest.mark.usefixtures("init_integration")
async def test_a_unit_without_home_leave_advertises_its_modes_alone(
    hass: HomeAssistant,
) -> None:
    """The widening belongs to the preset: no Home Leave, no away setpoints."""
    attributes = hass.states.get(ENTITY_ID).attributes

    assert ATTR_PRESET_MODES not in attributes
    assert attributes[ATTR_MIN_TEMP] == 16.0
    assert attributes[ATTR_MAX_TEMP] == 30.0


@pytest.mark.parametrize("aircon_fields", [model(64)])
@pytest.mark.usefixtures("init_integration")
async def test_a_unit_without_a_horizontal_vane_offers_neither_it_nor_3d(
    hass: HomeAssistant,
) -> None:
    """Ceiling cassettes have no horizontal vane, and 3D auto goes with it."""
    state = hass.states.get(ENTITY_ID)

    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & (
        ClimateEntityFeature.SWING_HORIZONTAL_MODE
    )
    assert ATTR_SWING_HORIZONTAL_MODES not in state.attributes
    assert SWING_3D_AUTO not in state.attributes[ATTR_SWING_MODES]


@pytest.mark.usefixtures("init_integration")
async def test_3d_auto_is_offered_as_a_vertical_swing_mode_only(
    hass: HomeAssistant,
) -> None:
    """3D auto drives both vanes and sits in one list, the vertical one."""
    attributes = hass.states.get(ENTITY_ID).attributes

    assert SWING_3D_AUTO in attributes[ATTR_SWING_MODES]
    assert SWING_3D_AUTO not in attributes[ATTR_SWING_HORIZONTAL_MODES]


@pytest.mark.parametrize(
    "aircon_fields",
    [{"Entrust": True, "WindDirectionLR": WindDirectionLR.POSITION_1}],
)
@pytest.mark.usefixtures("init_integration")
async def test_an_entrusted_unit_reports_3d_auto_and_its_horizontal_position(
    hass: HomeAssistant,
) -> None:
    """The horizontal vane keeps its raw position while 3D auto runs."""
    attributes = hass.states.get(ENTITY_ID).attributes

    assert attributes[ATTR_SWING_MODE] == SWING_3D_AUTO
    assert attributes[ATTR_SWING_HORIZONTAL_MODE] == "left_left"


@pytest.mark.parametrize(
    "aircon_fields",
    [
        {
            "Entrust": True,
            "WindDirectionUD": WindDirectionUD.POSITION_2,
            "WindDirectionLR": WindDirectionLR.POSITION_1,
        }
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_aiming_the_horizontal_vane_ends_3d_auto(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """The vertical vane stays where the unit had it."""
    await _call(
        hass,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {ATTR_SWING_HORIZONTAL_MODE: "right_right"},
    )

    assert _sent(mock_repository) == {
        AirconCommands.WindDirectionLR: WindDirectionLR.POSITION_5,
        AirconCommands.Entrust: False,
    }
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes[ATTR_SWING_MODE] == "middle"
    assert attributes[ATTR_SWING_HORIZONTAL_MODE] == "right_right"


@pytest.mark.parametrize(
    "aircon_fields",
    [{"Entrust": True, "WindDirectionLR": WIND_DIRECTION_UNKNOWN}],
)
@pytest.mark.usefixtures("init_integration")
async def test_an_entrusted_unit_with_an_unknown_horizontal_position(
    hass: HomeAssistant,
) -> None:
    """An unnamed horizontal position is unknown next to the 3D auto swing mode."""
    attributes = hass.states.get(ENTITY_ID).attributes

    assert attributes[ATTR_SWING_MODE] == SWING_3D_AUTO
    assert attributes[ATTR_SWING_HORIZONTAL_MODE] is None


@pytest.mark.usefixtures("init_integration")
async def test_preset_away_needs_a_direction(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """While the unit is off there is no cool-or-heat for Home Leave to mean."""
    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_AWAY})

    mock_repository.async_send_command.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_a_refused_command_reaches_the_caller(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """A blocking action reports a write the unit refused."""
    mock_repository.async_send_command.side_effect = WfRacCommandError("refused")

    with pytest.raises(HomeAssistantError, match="refused"):
        await _call(hass, SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "auto"})


@pytest.mark.usefixtures("init_integration")
async def test_commands_issued_together_become_one_command(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """Actions issued together leave as one request."""
    await asyncio.gather(
        _call(hass, SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.HEAT}),
        _call(hass, SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "auto"}),
    )

    mock_repository.async_send_command.assert_awaited_once()
    assert _sent(mock_repository) == {
        AirconCommands.OperationMode: OperationMode.HEAT,
        AirconCommands.Operation: True,
        AirconCommands.AirFlow: 0,
    }


@pytest.mark.parametrize(
    ("aircon_fields", "expected"),
    [
        pytest.param(
            {"Operation": True, "OperationMode": OperationMode.FAN},
            HVACAction.FAN,
            id="fan",
        ),
        pytest.param(
            {"Operation": True, "OperationMode": OperationMode.DRY},
            HVACAction.DRYING,
            id="dry",
        ),
        pytest.param(RUNNING_COOL, HVACAction.IDLE, id="satisfied"),
        pytest.param(
            {
                "Operation": True,
                "OperationMode": OperationMode.AUTO,
                "CompressorRunning": True,
                "CoolHotJudge": True,
            },
            HVACAction.HEATING,
            id="auto-heat",
        ),
        pytest.param(
            {
                "Operation": True,
                "OperationMode": OperationMode.AUTO,
                "CompressorRunning": True,
            },
            HVACAction.COOLING,
            id="auto-cool",
        ),
        pytest.param(
            {**RUNNING_COOL, "CompressorRunning": True}, HVACAction.COOLING, id="cool"
        ),
        pytest.param(
            {**RUNNING_HEAT, "CompressorRunning": True}, HVACAction.HEATING, id="heat"
        ),
        pytest.param({}, HVACAction.OFF, id="off"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_hvac_action(hass: HomeAssistant, expected: HVACAction) -> None:
    """CoolHotJudge is inverted against its raw bit, hence the explicit AUTO cases."""
    assert hass.states.get(ENTITY_ID).attributes["hvac_action"] is expected


@pytest.mark.parametrize(
    ("operation_mode", "expected"),
    [
        pytest.param(OperationMode.AUTO, HVACMode.AUTO, id="auto"),
        pytest.param(OperationMode.COOL, HVACMode.COOL, id="cool"),
        pytest.param(OperationMode.HEAT, HVACMode.HEAT, id="heat"),
        pytest.param(OperationMode.FAN, HVACMode.FAN_ONLY, id="fan_only"),
        pytest.param(OperationMode.DRY, HVACMode.DRY, id="dry"),
    ],
)
async def test_every_operation_mode_maps_to_an_hvac_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_repository: MagicMock,
    freezer: FrozenDateTimeFactory,
    operation_mode: OperationMode,
    expected: HVACMode,
) -> None:
    """The unit's mode byte, as Home Assistant names it."""
    status = mock_repository.async_get_status.return_value
    status.aircon = replace(status.aircon, Operation=True, OperationMode=operation_mode)

    await advance_polls(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.usefixtures("init_integration")
async def test_temperature_below_the_units_range_is_refused(
    hass: HomeAssistant,
) -> None:
    """The floor depends on the mode, and naming it is the whole message."""
    with pytest.raises(ServiceValidationError, match="heat"):
        await _call(
            hass,
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 17.0, ATTR_HVAC_MODE: HVACMode.HEAT},
        )


@pytest.mark.usefixtures("init_integration")
async def test_a_mode_the_unit_does_not_have_is_refused(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """A mode outside the entity's hvac_modes is refused, not looked up."""
    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 21.0, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        )

    mock_repository.async_send_command.assert_not_awaited()


@pytest.mark.parametrize(
    ("hvac_mode", "mode"),
    [
        pytest.param(HVACMode.HEAT, OperationMode.HEAT, id="on"),
        pytest.param(HVACMode.OFF, None, id="off sends no mode"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_setting_temperature_and_mode_together(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    hvac_mode: HVACMode,
    mode: OperationMode | None,
) -> None:
    """One call carries the setpoint and the mode it is for."""
    await _call(
        hass,
        SERVICE_SET_TEMPERATURE,
        {ATTR_TEMPERATURE: 19.0, ATTR_HVAC_MODE: hvac_mode},
    )

    assert _sent(mock_repository) == {
        AirconCommands.PresetTemp: 19.0,
        **({AirconCommands.OperationMode: mode} if mode is not None else {}),
        AirconCommands.Operation: hvac_mode != HVACMode.OFF,
    }


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.OFF}, id="mode"),
        pytest.param(
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 19.0, ATTR_HVAC_MODE: HVACMode.OFF},
            id="temperature",
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_turning_off_does_not_overwrite_a_mode_set_elsewhere(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    service: str,
    data: dict[str, Any],
) -> None:
    """After a lock refusal the frame is built from the unit's fresh state."""
    status = mock_repository.async_get_status.return_value
    mock_repository.fresh_state = replace(
        status.aircon, Operation=True, OperationMode=OperationMode.HEAT
    )

    await _call(hass, service, data)

    assert AirconCommands.OperationMode not in _sent(mock_repository)
    assert status.aircon.OperationMode == OperationMode.HEAT
    assert not status.aircon.Operation


@pytest.mark.parametrize(
    ("aircon_fields", "sends"),
    [
        pytest.param({"Vacant": True}, True, id="away"),
        pytest.param({"Vacant": False}, False, id="not_away"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_preset_none_returns_the_unit_to_a_normal_setpoint(
    hass: HomeAssistant, mock_repository: MagicMock, sends: bool
) -> None:
    """Leaving Home Leave is a setpoint, so outside it there is nothing to send."""
    await _call(hass, SERVICE_SET_PRESET_MODE, {ATTR_PRESET_MODE: PRESET_NONE})

    assert mock_repository.async_send_command.await_count == int(sends)


@pytest.mark.parametrize("aircon_fields", [WIDE_RANGE_HEATING])
@pytest.mark.usefixtures("init_integration")
async def test_a_model_with_the_wider_heating_range(hass: HomeAssistant) -> None:
    """PresetTempRange2 models heat down to 10 degrees, not 18."""
    await _call(hass, SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 10.0})

    assert hass.states.get(ENTITY_ID).attributes[ATTR_TEMPERATURE] == 10.0


@pytest.mark.parametrize(
    "aircon_fields",
    [
        pytest.param({**model(3), **RUNNING_COOL}, id="cooling"),
        pytest.param(WIDE_RANGE_HEATING, id="heating"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_the_advertised_range_spans_every_mode(hass: HomeAssistant) -> None:
    """The advertised range is the unit's whole range, not the running mode's."""
    attributes = hass.states.get(ENTITY_ID).attributes

    assert attributes[ATTR_MIN_TEMP] == 10
    assert attributes[ATTR_MAX_TEMP] == 33


@pytest.mark.parametrize(
    ("aircon_fields", "temperature"),
    [
        pytest.param(WIDE_RANGE_HEATING, 33.0, id="the cooling ceiling while heating"),
        pytest.param(
            {**model(3), **RUNNING_COOL}, 10.0, id="the heating floor while cooling"
        ),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_a_setpoint_outside_the_running_mode_is_refused(
    hass: HomeAssistant, temperature: float
) -> None:
    """A setpoint is held to its mode's own range."""
    with pytest.raises(ServiceValidationError):
        await _call(hass, SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: temperature})


@pytest.mark.parametrize("aircon_fields", [RUNNING_HEAT])
@pytest.mark.usefixtures("init_integration")
async def test_a_combined_call_is_measured_against_the_mode_it_switches_to(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """A combined call is measured against the mode it switches to."""
    await _call(
        hass,
        SERVICE_SET_TEMPERATURE,
        {ATTR_TEMPERATURE: 16.0, ATTR_HVAC_MODE: HVACMode.COOL},
    )

    assert _sent(mock_repository)[AirconCommands.PresetTemp] == 16.0


@pytest.mark.parametrize(
    ("aircon_fields", "temperature"),
    [
        pytest.param(model(1), 17.0, id="below_the_heating_floor"),
        pytest.param(model(3), 9.0, id="below_the_wide_heating_floor"),
        pytest.param(model(3), 32.0, id="above_the_heating_ceiling"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_a_setpoint_is_measured_against_the_mode_being_switched_to(
    hass: HomeAssistant, temperature: float
) -> None:
    """While off, the union range would pass values the target mode does not take."""
    with pytest.raises(ServiceValidationError):
        await _call(
            hass,
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: temperature, ATTR_HVAC_MODE: HVACMode.HEAT},
        )


@pytest.mark.parametrize(
    "aircon_fields",
    [
        {
            "AirFlow": AIRFLOW_UNKNOWN,
            "WindDirectionUD": WIND_DIRECTION_UNKNOWN,
            "WindDirectionLR": WIND_DIRECTION_UNKNOWN,
        }
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_unnamed_raw_values_leave_their_attributes_unknown(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The unit answered, so the entity stays available with unknown attributes."""
    state = hass.states.get(ENTITY_ID)

    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_FAN_MODE] is None
    assert state.attributes[ATTR_SWING_MODE] is None
    assert state.attributes[ATTR_SWING_HORIZONTAL_MODE] is None
    assert "Could not update" not in caplog.text


@pytest.mark.parametrize(
    "aircon_fields", [{"Operation": True, "OperationMode": OPERATION_MODE_UNKNOWN}]
)
@pytest.mark.usefixtures("init_integration")
async def test_an_unnamed_operation_mode_makes_the_state_unknown(
    hass: HomeAssistant,
) -> None:
    """Running in a mode with no member is unknown, not unavailable."""
    state = hass.states.get(ENTITY_ID)

    assert state.state == STATE_UNKNOWN
    assert ATTR_HVAC_ACTION not in state.attributes


@pytest.mark.usefixtures("init_integration")
async def test_a_later_frame_with_unnamed_values_turns_the_state_unknown_and_back(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unknown rather than unavailable: the unit answered and still takes commands."""
    status = mock_repository.async_get_status.return_value
    readable = status.aircon
    status.aircon = replace(
        readable, Operation=True, OperationMode=OPERATION_MODE_UNKNOWN
    )

    await advance_polls(hass, freezer, 3)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    status.aircon = readable
    await advance_polls(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF


@pytest.mark.parametrize(
    "aircon_fields", [{"Operation": True, "OperationMode": OperationMode.FAN}]
)
@pytest.mark.usefixtures("init_integration")
async def test_a_setpoint_sent_in_fan_only_is_held_to_every_modes_range(
    hass: HomeAssistant, mock_repository: MagicMock
) -> None:
    """Fan-only has no range of its own, so the union applies."""
    assert hass.states.get(ENTITY_ID).state == HVACMode.FAN_ONLY

    await _call(hass, SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 16.0})

    assert _sent(mock_repository)[AirconCommands.PresetTemp] == 16.0

    # The away setpoint belongs to the preset, not to a mode.
    mock_repository.async_send_command.reset_mock()
    with pytest.raises(ServiceValidationError):
        await _call(
            hass, SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: HOME_LEAVE_TEMP_HEAT}
        )

    mock_repository.async_send_command.assert_not_awaited()
