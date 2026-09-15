"""Test the Mitsubishi WF-RAC climate platform."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from pywfrac import AIRFLOW_UNKNOWN, Aircon, RacParser, WfRacError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
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

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "climate.living_room"


def _sent_command(mock_repository: AsyncMock) -> Aircon:
    """Decode the frame the integration last put on the wire.

    Command and status frames share a layout, so the same parser reads
    back what was encoded - which is what makes the protocol mapping
    (mode, setpoint, fan, louvers) assertable at all.
    """
    return RacParser().translate_bytes(
        mock_repository.send_airco_command.await_args.args[1]
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
    ("service", "data"),
    [
        (SERVICE_SET_HVAC_MODE, {ATTR_HVAC_MODE: HVACMode.COOL}),
        (SERVICE_SET_TEMPERATURE, {ATTR_TEMPERATURE: 21.0}),
        (SERVICE_SET_FAN_MODE, {ATTR_FAN_MODE: "auto"}),
        (SERVICE_SET_SWING_MODE, {ATTR_SWING_MODE: "highest"}),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_commands_reach_the_module(
    hass: HomeAssistant, mock_repository: AsyncMock, service: str, data: dict
) -> None:
    """Every setter ends up as one frame sent to the airco."""
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **data},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


@pytest.mark.usefixtures("init_integration")
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
    hass: HomeAssistant, mock_repository: AsyncMock, asked: float, sent: float
) -> None:
    """The frame carries int(PresetTemp / 0.5), and nothing validates the step.

    A value between two halves therefore reaches the unit as the lower one
    unless it is rounded here - 21.4 as 21.0, half a degree away from what was
    asked for.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: asked},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _sent_command(mock_repository).PresetTemp == sent


@pytest.mark.usefixtures("init_integration")
async def test_temperature_outside_the_units_range_is_refused(
    hass: HomeAssistant,
) -> None:
    """Refuse a setpoint the unit itself does not offer.

    Asking past the reported range is an error, not a value quietly clamped
    behind the user's back.
    """
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 40.0},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_without_a_single_setpoint(hass: HomeAssistant) -> None:
    """A range call has no single setpoint to send.

    The unit takes one target temperature, so the high/low pair the climate
    schema also accepts is refused rather than silently reduced to one of the
    two.
    """
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                "target_temp_low": 20.0,
                "target_temp_high": 24.0,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("operation_mode", "hvac_mode", "away_temp"),
    [
        pytest.param(1, HVACMode.COOL, HOME_LEAVE_TEMP_COOL, id="cooling"),
        pytest.param(2, HVACMode.HEAT, HOME_LEAVE_TEMP_HEAT, id="heating"),
    ],
)
async def test_preset_away_switches_the_unit_to_home_leave(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
    operation_mode: int,
    hvac_mode: HVACMode,
    away_temp: float,
) -> None:
    """Hand the away preset to the unit's own Home Leave mode.

    It is the unit's mode rather than a setpoint we invent: the unit enters it
    when it is given the away target of the direction it is running in, so the
    setpoint on the wire is what makes this work at all - and it differs
    between cooling and heating.

    The running state is set on the coordinator rather than driven through a
    command: the mocked module echoes one fixed status frame back, so a write
    would not change what the next read reports.
    """
    device = init_integration.runtime_data.device
    device.airco.Operation = True
    device.airco.OperationMode = operation_mode
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == hvac_mode
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_AWAY},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _sent_command(mock_repository).PresetTemp == away_temp


@pytest.mark.usefixtures("init_integration")
async def test_the_advertised_range_covers_the_away_setpoints(
    hass: HomeAssistant,
) -> None:
    """Home Leave runs at setpoints its mode's own table does not cover.

    The unit reports them back as the target temperature like any other, so a
    range stopping at the table would leave the entity reporting a target
    outside its own bounds for as long as Home Leave is on.
    """
    attributes = hass.states.get(ENTITY_ID).attributes

    # As a pair of bounds rather than two numbers: the snapshot already pins
    # what this model advertises, and what matters here is that the away
    # setpoints fall inside it however the range moves.
    assert attributes[ATTR_MIN_TEMP] <= HOME_LEAVE_TEMP_HEAT
    assert attributes[ATTR_MAX_TEMP] >= HOME_LEAVE_TEMP_COOL


@pytest.mark.usefixtures("mock_repository")
async def test_a_unit_without_home_leave_advertises_its_modes_alone(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aircon_stat: dict
) -> None:
    """The widening belongs to the preset: no Home Leave, no away setpoints."""
    airco = RacParser().translate_bytes(aircon_stat["airconStat"])
    airco.Capabilities = replace(airco.Capabilities, vacant_property=False)
    with patch.object(RacParser, "translate_bytes", return_value=airco):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    attributes = hass.states.get(ENTITY_ID).attributes

    assert ATTR_PRESET_MODES not in attributes
    assert attributes[ATTR_MIN_TEMP] == 16.0
    assert attributes[ATTR_MAX_TEMP] == 30.0


@pytest.mark.usefixtures("mock_repository")
async def test_a_unit_without_a_horizontal_vane_offers_neither_it_nor_3d(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aircon_stat: dict
) -> None:
    """Ceiling cassettes have no left/right vane, and the manufacturer says so.

    3D auto goes with it: it is the unit taking over both vanes, so a model
    line without the horizontal one cannot be handed them. Offering either
    would be offering a command the unit cannot carry out.
    """
    airco = RacParser().translate_bytes(aircon_stat["airconStat"])
    airco.Capabilities = replace(
        airco.Capabilities, wind_direction_lr=False, entrust=False
    )
    with patch.object(RacParser, "translate_bytes", return_value=airco):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & (
        ClimateEntityFeature.SWING_HORIZONTAL_MODE
    )
    assert ATTR_SWING_HORIZONTAL_MODES not in state.attributes
    assert SWING_3D_AUTO not in state.attributes[ATTR_SWING_MODES]


@pytest.mark.usefixtures("mock_repository")
async def test_a_unit_that_cannot_be_entrusted_keeps_its_own_vanes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aircon_stat: dict
) -> None:
    """3D auto is gated on its own capability, not on the horizontal vane."""
    airco = RacParser().translate_bytes(aircon_stat["airconStat"])
    airco.Capabilities = replace(airco.Capabilities, entrust=False)
    with patch.object(RacParser, "translate_bytes", return_value=airco):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    attributes = hass.states.get(ENTITY_ID).attributes

    assert SWING_3D_AUTO not in attributes[ATTR_SWING_MODES]
    assert SWING_3D_AUTO not in attributes[ATTR_SWING_HORIZONTAL_MODES]
    assert attributes[ATTR_SWING_HORIZONTAL_MODES]


@pytest.mark.usefixtures("init_integration")
async def test_preset_away_needs_a_direction(hass: HomeAssistant) -> None:
    """While the unit is off there is no cool-or-heat for Home Leave to mean."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_AWAY},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_and_off(hass: HomeAssistant, mock_repository: AsyncMock) -> None:
    """Turning off keeps the mode, so turning on again returns to it."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_repository.send_airco_command.assert_awaited()

    mock_repository.send_airco_command.reset_mock()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_repository.send_airco_command.assert_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_horizontal_swing(
    hass: HomeAssistant, mock_repository: AsyncMock
) -> None:
    """The left/right louver is its own axis on this hardware."""
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_HORIZONTAL_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_SWING_HORIZONTAL_MODE: "left_left"},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_a_refused_command_reaches_the_caller(
    hass: HomeAssistant, mock_repository: AsyncMock
) -> None:
    """A blocking action reports a write the unit did not take.

    The command is queued and flushed on a task, so this only holds because
    the caller awaits that task - see Device.async_queue_command().
    """
    mock_repository.send_airco_command.side_effect = WfRacError("refused")

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_commands_issued_together_become_one_frame(
    hass: HomeAssistant, mock_repository: AsyncMock
) -> None:
    """Two actions issued together still leave as one frame.

    Every command is awaited to its result now, so this only holds because
    the platform does not serialise them on top of that: with
    PARALLEL_UPDATES = 1 the second call would not start until the first had
    been sent, and the consolidation window would be over. Commands issued
    one after another - a script awaiting each step - do leave separately;
    there is no window to join once the first has been sent and answered.
    """
    mock_repository.send_airco_command.reset_mock()

    await asyncio.gather(
        hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.HEAT},
            blocking=True,
        ),
        hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_FAN_MODE: "auto"},
            blocking=True,
        ),
    )
    await hass.async_block_till_done()

    assert mock_repository.send_airco_command.await_count == 1


@pytest.mark.parametrize(
    ("operation_mode", "compressor", "cool_hot_judge", "expected"),
    [
        (3, False, False, HVACAction.FAN),
        (4, False, False, HVACAction.DRYING),
        (1, False, False, HVACAction.IDLE),
        (0, True, True, HVACAction.HEATING),
        (0, True, False, HVACAction.COOLING),
        (1, True, False, HVACAction.COOLING),
        (2, True, False, HVACAction.HEATING),
    ],
    ids=["fan", "dry", "satisfied", "auto-heat", "auto-cool", "cool", "heat"],
)
async def test_hvac_action_while_running(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    operation_mode: int,
    compressor: bool,
    cool_hot_judge: bool,
    expected: HVACAction,
) -> None:
    """What the unit reports it is doing, per mode.

    CoolHotJudge is inverted against its raw bit, which is why the two AUTO
    cases are spelled out rather than left to the reader.
    """
    device = init_integration.runtime_data.device
    device.airco.Operation = True
    device.airco.OperationMode = operation_mode
    device.airco.CompressorRunning = compressor
    device.airco.CoolHotJudge = cool_hot_judge
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["hvac_action"] is expected


@pytest.mark.usefixtures("init_integration")
async def test_hvac_action_is_off_while_the_unit_is(hass: HomeAssistant) -> None:
    """The captured frame has the unit off."""
    assert hass.states.get(ENTITY_ID).attributes["hvac_action"] is HVACAction.OFF


@pytest.mark.parametrize(
    ("operation_mode", "expected"),
    [
        (0, HVACMode.AUTO),
        (1, HVACMode.COOL),
        (2, HVACMode.HEAT),
        (3, HVACMode.FAN_ONLY),
        (4, HVACMode.DRY),
    ],
)
async def test_every_operation_mode_maps_to_an_hvac_mode(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    operation_mode: int,
    expected: HVACMode,
) -> None:
    """The unit's mode byte, as Home Assistant names it."""
    device = init_integration.runtime_data.device
    device.airco.Operation = True
    device.airco.OperationMode = operation_mode
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.usefixtures("init_integration")
async def test_temperature_below_the_units_range_is_refused(
    hass: HomeAssistant,
) -> None:
    """The floor depends on the mode, and naming it is the whole message."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 5.0,
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("init_integration")
async def test_a_mode_the_unit_does_not_have_is_refused(
    hass: HomeAssistant, mock_repository: AsyncMock
) -> None:
    """The combined call takes any mode of the enum, this unit has six.

    Nothing between the service and the entity holds hvac_mode to the modes
    the entity advertises, so heat_cool arrives here and must come back as a
    validation error rather than as a lookup that fails.
    """
    mock_repository.send_airco_command.reset_mock()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 21.0,
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
            },
            blocking=True,
        )

    mock_repository.send_airco_command.assert_not_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_setting_temperature_and_mode_together(
    hass: HomeAssistant, mock_repository: AsyncMock
) -> None:
    """A setpoint measured against the mode the call switches to.

    The range depends on the mode, and an automation that sets both at once
    must not be judged against the mode the unit is leaving.
    """
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 19.0,
            ATTR_HVAC_MODE: HVACMode.HEAT,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


@pytest.mark.usefixtures("init_integration")
async def test_preset_none_returns_the_unit_to_a_normal_setpoint(
    hass: HomeAssistant, mock_repository: AsyncMock
) -> None:
    """Leaving Home Leave is a setpoint, not a mode of its own."""
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


@pytest.mark.parametrize(
    ("service", "attribute"),
    [
        (SERVICE_SET_SWING_MODE, ATTR_SWING_MODE),
        (SERVICE_SET_SWING_HORIZONTAL_MODE, ATTR_SWING_HORIZONTAL_MODE),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_3d_auto_hands_both_louvers_to_the_unit(
    hass: HomeAssistant, mock_repository: AsyncMock, service: str, attribute: str
) -> None:
    """3D auto is the unit's own vane logic, entrusted from either axis."""
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, attribute: SWING_3D_AUTO},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


async def test_a_model_with_the_wider_heating_range(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """PresetTempRange2 models heat down to 10 degrees, not 18."""
    device = init_integration.runtime_data.device
    device.airco.Capabilities = replace(
        device.airco.Capabilities, preset_temp_range_2=True
    )
    device.airco.Operation = True
    device.airco.OperationMode = 2
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["min_temp"] == 10


@pytest.mark.parametrize(
    "operation_mode",
    [pytest.param(1, id="cooling"), pytest.param(2, id="heating")],
)
async def test_the_advertised_range_spans_every_mode(
    hass: HomeAssistant, init_integration: MockConfigEntry, operation_mode: int
) -> None:
    """What is advertised is the unit's whole range, not the running mode's.

    climate measures a service call against min_temp/max_temp before the
    entity sees hvac_mode, so a range that followed the running mode would
    refuse a call that states a different one outright.
    """
    device = init_integration.runtime_data.device
    device.airco.Capabilities = replace(
        device.airco.Capabilities, preset_temp_range_2=True
    )
    device.airco.Operation = True
    device.airco.OperationMode = operation_mode
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes["min_temp"] == 10
    assert attributes["max_temp"] == 33


@pytest.mark.parametrize(
    ("operation_mode", "temperature"),
    [
        pytest.param(2, 33.0, id="the cooling ceiling while heating"),
        pytest.param(1, 10.0, id="the heating floor while cooling"),
    ],
)
async def test_a_setpoint_outside_the_running_mode_is_refused(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    operation_mode: int,
    temperature: float,
) -> None:
    """The mode's own range is what a setpoint is held to when it is sent.

    Both values are inside the advertised range, so the refusal has to come
    from the entity - naming the mode, which is what tells the user their
    value belongs in the other one.
    """
    device = init_integration.runtime_data.device
    device.airco.Capabilities = replace(
        device.airco.Capabilities, preset_temp_range_2=True
    )
    device.airco.Operation = True
    device.airco.OperationMode = operation_mode
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
            blocking=True,
        )


async def test_a_combined_call_is_measured_against_the_mode_it_switches_to(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Cooling's floor is reachable while the unit is still heating.

    The heating floor is 18 and cooling's is 16, and this call says which mode
    it is for. It has to reach the unit rather than be measured against the
    mode it is leaving.
    """
    device = init_integration.runtime_data.device
    device.airco.Operation = True
    device.airco.OperationMode = 2
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()
    mock_repository.send_airco_command.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 16.0,
            ATTR_HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_repository.send_airco_command.assert_awaited()


async def test_a_frame_the_entity_cannot_read_makes_its_state_unknown(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A frame the entity cannot read ends at the entity.

    Unknown rather than unavailable: the unit answered and still takes
    commands, and Home Assistant leaves unavailable entities out of entity
    service calls - so reporting unavailable would take the controls away
    from a unit that is right there.
    """
    device = init_integration.runtime_data.device
    device.airco.OperationMode = 99
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    # And back, without waiting out anything: the next frame it can read is
    # all it needs.
    device.airco.OperationMode = 1
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == HVACMode.OFF


@pytest.mark.parametrize(
    ("capability", "temperature", "hvac_mode"),
    [
        pytest.param(False, 17.0, HVACMode.HEAT, id="below_the_heating_floor"),
        pytest.param(True, 32.0, HVACMode.HEAT, id="above_the_heating_ceiling"),
    ],
)
async def test_a_setpoint_is_measured_against_the_mode_being_switched_to(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    capability: bool,
    temperature: float,
    hvac_mode: HVACMode,
) -> None:
    """One call that sets both is measured against the mode it is switching to.

    While the unit is off the range spans every regulating mode, so these
    values pass the entity's own min_temp/max_temp - and would arrive at a
    unit that does not take them. Naming the mode in the refusal is the point:
    the same value is fine in the mode the automation was leaving.
    """
    device = init_integration.runtime_data.device
    device.airco.Capabilities = replace(
        device.airco.Capabilities, preset_temp_range_2=capability
    )
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: temperature,
                ATTR_HVAC_MODE: hvac_mode,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_repository")
async def test_a_frame_the_entity_cannot_read_still_produces_an_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, aircon_stat: dict
) -> None:
    """An unreadable first frame makes the state unknown, not the entity absent.

    The first read happens in the constructor, so an exception there does not
    just make one entity unavailable - it aborts the platform setup and leaves
    the config entry loaded with no entities at all, and nothing but a
    traceback to say why. A fan value the library could not translate is the
    one such value a real frame can carry.
    """
    airco = RacParser().translate_bytes(aircon_stat["airconStat"])
    airco.AirFlow = AIRFLOW_UNKNOWN
    with patch.object(RacParser, "translate_bytes", return_value=airco):
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_a_setpoint_sent_in_fan_only_is_held_to_every_modes_range(
    hass: HomeAssistant,
    mock_repository: AsyncMock,
    init_integration: MockConfigEntry,
) -> None:
    """Fan-only has no setpoint range of its own, so the union applies.

    The value is stored for whichever regulating mode is turned on next, and
    holding it to the default floor would refuse a cooling setpoint the unit
    takes happily once it is cooling.
    """
    device = init_integration.runtime_data.device
    device.airco.Operation = True
    device.airco.OperationMode = 3
    device.async_set_updated_data(device.airco)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.FAN_ONLY

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 16.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert _sent_command(mock_repository).PresetTemp == 16.0

    # The away setpoint is inside the advertised range but belongs to the
    # preset, not to a mode: the union is still what a value sent here is
    # held to.
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: HOME_LEAVE_TEMP_HEAT},
            blocking=True,
        )
