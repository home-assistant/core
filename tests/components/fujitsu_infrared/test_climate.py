"""Tests for the Fujitsu Infrared climate platform."""

from typing import Any
from unittest.mock import patch

from infrared_protocols.codes.fujitsu.ac import FujitsuACCode
from infrared_protocols.commands.fujitsu_ac import (
    MIN_TEMP,
    FujitsuAcCommand,
    FujitsuAcFanSpeed,
    FujitsuAcMode,
    FujitsuAcProtocol,
    FujitsuAcSwing,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_SWING_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.fujitsu_infrared.climate import FAN_QUIET
from homeassistant.components.fujitsu_infrared.const import (
    PROTOCOL_EXTENDED,
    PROTOCOL_STANDARD,
)
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import MockConfigEntry, mock_restore_cache, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

_CLIMATE_ENTITY_ID = "climate.fujitsu_ac"

_ALL_MODES = [
    HVACMode.COOL,
    HVACMode.HEAT,
    HVACMode.DRY,
    HVACMode.FAN_ONLY,
    HVACMode.HEAT_COOL,
]


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.CLIMATE]


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return False


async def _set_hvac_mode(hass: HomeAssistant, hvac_mode: HVACMode) -> None:
    """Call the set_hvac_mode action on the climate entity."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )


def _sent_timings(emitter: MockInfraredEmitterEntity) -> list[int]:
    """Return the raw timings of the single command the emitter was given."""
    assert len(emitter.send_command_calls) == 1
    return emitter.send_command_calls[0].get_raw_timings()


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity state and registry snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_availability_follows_emitter(hass: HomeAssistant) -> None:
    """Test climate entity availability follows the infrared emitter."""
    await assert_availability_follows_source_entity(
        hass, _CLIMATE_ENTITY_ID, EMITTER_ENTITY_ID
    )


@pytest.mark.usefixtures("init_integration")
async def test_supported_features(hass: HomeAssistant) -> None:
    """Test every state field is offered, since every mode's message carries them."""
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["supported_features"] == (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_off(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test turning off sends the power-off message, which carries no state."""
    await _set_hvac_mode(hass, HVACMode.OFF)

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuACCode.POWER_OFF.to_command().get_raw_timings()
    )


@pytest.mark.parametrize("hvac_modes", [_ALL_MODES])
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "lib_mode"),
    [
        pytest.param(HVACMode.COOL, FujitsuAcMode.COOL, id="cool"),
        pytest.param(HVACMode.HEAT, FujitsuAcMode.HEAT, id="heat"),
        pytest.param(HVACMode.DRY, FujitsuAcMode.DRY, id="dry"),
        pytest.param(HVACMode.FAN_ONLY, FujitsuAcMode.FAN_ONLY, id="fan_only"),
        pytest.param(HVACMode.HEAT_COOL, FujitsuAcMode.AUTO, id="heat_cool"),
    ],
)
async def test_set_hvac_mode_from_off_sets_power_flag(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    lib_mode: FujitsuAcMode,
) -> None:
    """Test every mode encodes correctly and starts a unit that is off."""
    await _set_hvac_mode(hass, hvac_mode)

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(
            power=True, mode=lib_mode, temperature=MIN_TEMP
        ).get_raw_timings()
    )


@pytest.mark.parametrize("hvac_modes", [_ALL_MODES])
@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_while_running_clears_power_flag(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test a running unit is not sent the flag that starts it."""
    await _set_hvac_mode(hass, HVACMode.COOL)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await _set_hvac_mode(hass, HVACMode.HEAT)

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(
            mode=FujitsuAcMode.HEAT, temperature=MIN_TEMP
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_sends_command_when_active(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test set_temperature sends the whole state while the AC is on."""
    await _set_hvac_mode(hass, HVACMode.COOL)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 26},
        blocking=True,
    )

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(mode=FujitsuAcMode.COOL, temperature=26).get_raw_timings()
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 26.0


@pytest.mark.parametrize("protocol", [PROTOCOL_EXTENDED])
@pytest.mark.usefixtures("init_integration")
async def test_extended_protocol_offers_half_degree_steps(hass: HomeAssistant) -> None:
    """Test a half-degree remote advertises the step it can actually send."""
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["target_temp_step"] == 0.5


@pytest.mark.parametrize("protocol", [PROTOCOL_EXTENDED])
@pytest.mark.usefixtures("init_integration")
async def test_extended_protocol_sends_half_degrees(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test a half-degree setpoint reaches the emitter unrounded."""
    await _set_hvac_mode(hass, HVACMode.COOL)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 24.5},
        blocking=True,
    )

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(
            protocol=FujitsuAcProtocol.EXTENDED,
            mode=FujitsuAcMode.COOL,
            temperature=24.5,
        ).get_raw_timings()
    )


@pytest.mark.parametrize(
    ("protocol", "requested", "expected"),
    [
        pytest.param(
            PROTOCOL_STANDARD, 24.5, 24.0, id="standard_rounds_a_half_degree_away"
        ),
        pytest.param(PROTOCOL_EXTENDED, 24.2, 24.0, id="extended_rounds_down"),
        pytest.param(PROTOCOL_EXTENDED, 24.4, 24.5, id="extended_rounds_up"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_temperature_is_snapped_to_a_step_the_remote_can_send(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    requested: float,
    expected: float,
) -> None:
    """Test a setpoint finer than the protocol allows is rounded, not rejected.

    Home Assistant does not enforce the step, so a whole-degree remote can be asked
    for 24.5 and has no field to put the half in.
    """
    await _set_hvac_mode(hass, HVACMode.COOL)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: requested},
        blocking=True,
    )

    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert isinstance(command, FujitsuAcCommand)
    assert command.temperature == expected


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_no_command_when_off(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test set_temperature updates state but sends nothing while the AC is off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 22},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 22.0


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test set_temperature switches mode when one is given, even while off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
            ATTR_TEMPERATURE: 24,
            ATTR_HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(
            power=True, mode=FujitsuAcMode.COOL, temperature=24
        ).get_raw_timings()
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_TEMPERATURE] == 24.0


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_hvac_mode_off(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test set_temperature turns the unit off when it is given the off mode."""
    await _set_hvac_mode(hass, HVACMode.COOL)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
            ATTR_TEMPERATURE: 24,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuACCode.POWER_OFF.to_command().get_raw_timings()
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_TEMPERATURE] == 24.0


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_unsupported_hvac_mode(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test a mode the unit does not support is rejected instead of sent."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
                ATTR_TEMPERATURE: 24,
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("fan_mode", "lib_fan"),
    [
        pytest.param(FAN_AUTO, FujitsuAcFanSpeed.AUTO, id="auto"),
        pytest.param(FAN_QUIET, FujitsuAcFanSpeed.QUIET, id="quiet"),
        pytest.param(FAN_LOW, FujitsuAcFanSpeed.LOW, id="low"),
        pytest.param(FAN_MEDIUM, FujitsuAcFanSpeed.MEDIUM, id="medium"),
        pytest.param(FAN_HIGH, FujitsuAcFanSpeed.HIGH, id="high"),
    ],
)
async def test_set_fan_mode_sends_command_when_active(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    fan_mode: str,
    lib_fan: FujitsuAcFanSpeed,
) -> None:
    """Test every fan speed encodes correctly while the AC is on."""
    await _set_hvac_mode(hass, HVACMode.COOL)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_FAN_MODE: fan_mode},
        blocking=True,
    )

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(
            mode=FujitsuAcMode.COOL, temperature=MIN_TEMP, fan=lib_fan
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode_no_command_when_off(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test set_fan_mode updates state but sends nothing while the AC is off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_FAN_MODE: FAN_HIGH},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_FAN_MODE] == FAN_HIGH


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("swing_mode", "lib_swing"),
    [
        pytest.param(SWING_OFF, FujitsuAcSwing.OFF, id="off"),
        pytest.param(SWING_VERTICAL, FujitsuAcSwing.VERTICAL, id="vertical"),
        pytest.param(SWING_HORIZONTAL, FujitsuAcSwing.HORIZONTAL, id="horizontal"),
        pytest.param(SWING_BOTH, FujitsuAcSwing.BOTH, id="both"),
    ],
)
async def test_swing_mode_maps_to_the_protocol_field(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    swing_mode: str,
    lib_swing: FujitsuAcSwing,
) -> None:
    """Test each swing mode reaches the single two-bit protocol field."""
    await _set_hvac_mode(hass, HVACMode.COOL)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_SWING_MODE: swing_mode},
        blocking=True,
    )

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(
            mode=FujitsuAcMode.COOL, temperature=MIN_TEMP, swing=lib_swing
        ).get_raw_timings()
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_SWING_MODE] == swing_mode


@pytest.mark.usefixtures("init_integration")
async def test_set_swing_no_command_when_off(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test the swing action updates state but sends nothing while the AC is off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_SWING_MODE: SWING_BOTH},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_SWING_MODE] == SWING_BOTH


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("lib_fan", "expected_fan_mode"),
    [
        pytest.param(FujitsuAcFanSpeed.AUTO, FAN_AUTO, id="auto"),
        pytest.param(FujitsuAcFanSpeed.QUIET, FAN_QUIET, id="quiet"),
        pytest.param(FujitsuAcFanSpeed.LOW, FAN_LOW, id="low"),
        pytest.param(FujitsuAcFanSpeed.MEDIUM, FAN_MEDIUM, id="medium"),
        pytest.param(FujitsuAcFanSpeed.HIGH, FAN_HIGH, id="high"),
    ],
)
async def test_receiver_updates_state_on_cool_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    lib_fan: FujitsuAcFanSpeed,
    expected_fan_mode: str,
) -> None:
    """Test a received cool signal updates mode, temperature, fan and swing."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=FujitsuAcCommand(
                mode=FujitsuAcMode.COOL,
                temperature=24,
                fan=lib_fan,
                swing=FujitsuAcSwing.BOTH,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ATTR_FAN_MODE] == expected_fan_mode
    assert state.attributes[ATTR_TEMPERATURE] == 24.0
    assert state.attributes[ATTR_SWING_MODE] == SWING_BOTH


@pytest.mark.parametrize("protocol", [PROTOCOL_EXTENDED])
@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_converts_a_fahrenheit_signal(
    hass: HomeAssistant, mock_infrared_receiver_entity: MockInfraredReceiverEntity
) -> None:
    """Test a remote set to Fahrenheit updates the Celsius entity correctly.

    75 F is what the remote displays. Converted it is 23.89 C, which is not a setpoint
    this entity can send back, so it lands on the nearest half degree.
    """
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=FujitsuAcCommand(
                protocol=FujitsuAcProtocol.EXTENDED,
                mode=FujitsuAcMode.COOL,
                temperature=75,
                is_fahrenheit=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 24.0


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_updates_state_on_off_signal(
    hass: HomeAssistant, mock_infrared_receiver_entity: MockInfraredReceiverEntity
) -> None:
    """Test a received off signal sets mode to off, preserving the other state.

    The power-off message carries no state, so the last known values must survive it.
    """
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=FujitsuAcCommand(
                mode=FujitsuAcMode.COOL,
                temperature=24,
                fan=FujitsuAcFanSpeed.MEDIUM,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=FujitsuACCode.POWER_OFF.to_command().get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_FAN_MODE] == FAN_MEDIUM
    assert state.attributes[ATTR_TEMPERATURE] == 24.0


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_unconfigured_hvac_mode(
    hass: HomeAssistant, mock_infrared_receiver_entity: MockInfraredReceiverEntity
) -> None:
    """Test a signal for a mode the user did not configure does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=FujitsuAcCommand(
                mode=FujitsuAcMode.HEAT,
                temperature=24,
                fan=FujitsuAcFanSpeed.HIGH,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_another_protocol_family(
    hass: HomeAssistant, mock_infrared_receiver_entity: MockInfraredReceiverEntity
) -> None:
    """Test a frame from the other remote family does not change state.

    The entry is configured for the standard protocol, so an extended frame belongs to
    a different unit and the configured one ignores it too.
    """
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=FujitsuAcCommand(
                protocol=FujitsuAcProtocol.EXTENDED,
                mode=FujitsuAcMode.COOL,
                temperature=29,
                fan=FujitsuAcFanSpeed.HIGH,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes[ATTR_FAN_MODE] == FAN_AUTO


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_unrecognised_signal(
    hass: HomeAssistant, mock_infrared_receiver_entity: MockInfraredReceiverEntity
) -> None:
    """Test an unrecognised IR signal does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[500, -500, 300, -300])
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.parametrize(
    ("restored_state", "restored_attributes", "expected"),
    [
        pytest.param(
            HVACMode.COOL,
            {
                ATTR_FAN_MODE: FAN_HIGH,
                ATTR_TEMPERATURE: 29.0,
                ATTR_SWING_MODE: SWING_BOTH,
            },
            (HVACMode.COOL, FAN_HIGH, 29.0, SWING_BOTH),
            id="full_state",
        ),
        pytest.param(
            STATE_UNAVAILABLE,
            {},
            (HVACMode.OFF, FAN_AUTO, float(MIN_TEMP), SWING_OFF),
            id="unavailable_falls_back_to_defaults",
        ),
        pytest.param(
            HVACMode.HEAT,
            {ATTR_FAN_MODE: FAN_HIGH, ATTR_TEMPERATURE: 29.0},
            (HVACMode.OFF, FAN_HIGH, 29.0, SWING_OFF),
            id="mode_no_longer_configured_is_ignored",
        ),
    ],
)
async def test_state_restored_on_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    restored_state: str,
    restored_attributes: dict[str, Any],
    expected: tuple[HVACMode, str, float, str],
) -> None:
    """Test the assumed state is restored, since infrared cannot read it back."""
    mock_restore_cache(
        hass, [State(_CLIMATE_ENTITY_ID, restored_state, restored_attributes)]
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.fujitsu_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    expected_mode, expected_fan, expected_temp, expected_swing = expected
    assert state.state == expected_mode
    assert state.attributes[ATTR_FAN_MODE] == expected_fan
    assert state.attributes[ATTR_TEMPERATURE] == expected_temp
    assert state.attributes[ATTR_SWING_MODE] == expected_swing


async def test_fahrenheit_temperatures_round_trip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
) -> None:
    """Test a restored temperature converts to Celsius on a Fahrenheit installation."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_restore_cache(
        hass, [State(_CLIMATE_ENTITY_ID, HVACMode.COOL, {ATTR_TEMPERATURE: 75})]
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.fujitsu_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_TEMPERATURE] == 75

    mock_infrared_emitter_entity.send_command_calls.clear()
    await _set_hvac_mode(hass, HVACMode.COOL)

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(mode=FujitsuAcMode.COOL, temperature=24).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_restored_state_is_sent_with_the_next_command(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Test state set while the AC is off is carried by the message that starts it."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 27},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_FAN_MODE: FAN_LOW},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_SWING_MODE: SWING_BOTH},
        blocking=True,
    )
    assert len(mock_infrared_emitter_entity.send_command_calls) == 0

    await _set_hvac_mode(hass, HVACMode.COOL)

    assert (
        _sent_timings(mock_infrared_emitter_entity)
        == FujitsuAcCommand(
            power=True,
            mode=FujitsuAcMode.COOL,
            temperature=27,
            fan=FujitsuAcFanSpeed.LOW,
            swing=FujitsuAcSwing.BOTH,
        ).get_raw_timings()
    )
