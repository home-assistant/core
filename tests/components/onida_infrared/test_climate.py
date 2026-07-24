"""Tests for the Onida Infrared climate platform."""

from typing import Any
from unittest.mock import patch

from infrared_protocols.commands.onida_ac import (
    MIN_TEMP,
    OnidaAcCommand,
    OnidaAcFanSpeed,
    OnidaAcMode,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACMode,
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

from tests.common import MockConfigEntry, mock_restore_cache, snapshot_platform
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

_CLIMATE_ENTITY_ID = "climate.onida_ac"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.CLIMATE]


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return False


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
async def test_availability_follows_emitter(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test climate entity availability follows the infrared emitter."""
    await assert_availability_follows_source_entity(
        hass, _CLIMATE_ENTITY_ID, EMITTER_ENTITY_ID
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test setting HVAC mode to off sends a power-off frame with the default mode.

    The protocol has no dedicated off mode, so the frame still carries a mode; before
    any mode has been active, that is the first configured mode.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == OnidaAcCommand(
            power=False,
            mode=OnidaAcMode.COOL,
            temperature=MIN_TEMP,
            fan=OnidaAcFanSpeed.AUTO,
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "temp", "fan", "expected_cmd"),
    [
        pytest.param(
            HVACMode.COOL,
            24,
            FAN_AUTO,
            OnidaAcCommand(
                mode=OnidaAcMode.COOL, temperature=24, fan=OnidaAcFanSpeed.AUTO
            ),
            id="cool_24_auto",
        ),
        pytest.param(
            HVACMode.COOL,
            18,
            FAN_LOW,
            OnidaAcCommand(
                mode=OnidaAcMode.COOL, temperature=18, fan=OnidaAcFanSpeed.LOW
            ),
            id="cool_18_low",
        ),
        pytest.param(
            HVACMode.COOL,
            30,
            FAN_HIGH,
            OnidaAcCommand(
                mode=OnidaAcMode.COOL, temperature=30, fan=OnidaAcFanSpeed.HIGH
            ),
            id="cool_30_high",
        ),
        pytest.param(
            HVACMode.DRY,
            24,
            FAN_MEDIUM,
            OnidaAcCommand(
                mode=OnidaAcMode.DRY, temperature=24, fan=OnidaAcFanSpeed.MEDIUM
            ),
            id="dry_24_medium",
        ),
    ],
)
async def test_set_hvac_mode_encodes_correctly(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    temp: int,
    fan: str,
    expected_cmd: OnidaAcCommand,
) -> None:
    """Test that set_hvac_mode sends correctly encoded timings."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: temp},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": fan},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_cmd.get_raw_timings()


@pytest.mark.parametrize(
    "hvac_modes",
    [[HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.AUTO]],
)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "expected_cmd"),
    [
        pytest.param(
            HVACMode.HEAT,
            OnidaAcCommand(
                mode=OnidaAcMode.HEAT, temperature=MIN_TEMP, fan=OnidaAcFanSpeed.AUTO
            ),
            id="heat",
        ),
        pytest.param(
            HVACMode.FAN_ONLY,
            OnidaAcCommand(
                mode=OnidaAcMode.FAN_ONLY,
                temperature=MIN_TEMP,
                fan=OnidaAcFanSpeed.AUTO,
            ),
            id="fan_only",
        ),
        pytest.param(
            HVACMode.AUTO,
            OnidaAcCommand(
                mode=OnidaAcMode.AUTO, temperature=MIN_TEMP, fan=OnidaAcFanSpeed.AUTO
            ),
            id="auto",
        ),
    ],
)
async def test_set_hvac_mode_from_off_uses_defaults(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    expected_cmd: OnidaAcCommand,
) -> None:
    """Test modes not reachable via the cool/dry default encode from entity defaults."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_cmd.get_raw_timings()


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_sends_command_when_active(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature sends IR when AC is on."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 26},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == OnidaAcCommand(
            mode=OnidaAcMode.COOL, temperature=26, fan=OnidaAcFanSpeed.AUTO
        ).get_raw_timings()
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert float(state.attributes["temperature"]) == 26.0


@pytest.mark.parametrize("hvac_modes", [[HVACMode.DRY]])
@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_sends_command_in_dry_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test dry mode sends IR on temperature change.

    The temperature field is present in every mode's frame, so a temperature change
    is always transmittable.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == OnidaAcCommand(
            mode=OnidaAcMode.DRY, temperature=25, fan=OnidaAcFanSpeed.AUTO
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_no_command_when_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature updates state but sends no IR when AC is off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 22},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert float(state.attributes["temperature"]) == 22.0


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode_sends_command_when_active(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_fan_mode sends IR when AC is on."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_HIGH},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == OnidaAcCommand(
            mode=OnidaAcMode.COOL, temperature=MIN_TEMP, fan=OnidaAcFanSpeed.HIGH
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_fan_mode_no_command_when_off(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_fan_mode updates state but sends no IR when AC is off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_HIGH},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["fan_mode"] == FAN_HIGH


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("lib_fan", "expected_fan_mode"),
    [
        pytest.param(OnidaAcFanSpeed.AUTO, FAN_AUTO, id="auto"),
        pytest.param(OnidaAcFanSpeed.LOW, FAN_LOW, id="low"),
        pytest.param(OnidaAcFanSpeed.MEDIUM, FAN_MEDIUM, id="medium"),
        pytest.param(OnidaAcFanSpeed.HIGH, FAN_HIGH, id="high"),
    ],
)
async def test_receiver_updates_state_on_cool_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    lib_fan: OnidaAcFanSpeed,
    expected_fan_mode: str,
) -> None:
    """Test that a received cool signal updates mode, temperature and every fan speed."""
    timings = OnidaAcCommand(
        mode=OnidaAcMode.COOL, temperature=24, fan=lib_fan
    ).get_raw_timings()

    signal = InfraredReceivedSignal(timings=timings)
    mock_infrared_receiver_entity._handle_received_signal(signal)
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes["fan_mode"] == expected_fan_mode
    assert float(state.attributes["temperature"]) == 24.0


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_updates_state_on_off_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a received off signal sets mode to off, preserving temperature and fan."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=OnidaAcCommand(
                mode=OnidaAcMode.COOL, temperature=24, fan=OnidaAcFanSpeed.MEDIUM
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=OnidaAcCommand(
                power=False,
                mode=OnidaAcMode.COOL,
                temperature=24,
                fan=OnidaAcFanSpeed.MEDIUM,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes["fan_mode"] == FAN_MEDIUM
    assert float(state.attributes["temperature"]) == 24.0


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_unconfigured_hvac_mode(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a signal for a mode the user did not configure does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=OnidaAcCommand(
                mode=OnidaAcMode.HEAT, temperature=24, fan=OnidaAcFanSpeed.HIGH
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes["fan_mode"] == FAN_AUTO


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_non_onida_ac_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test that an unrecognised IR signal does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(timings=[500, -500, 300, -300])
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
async def test_supported_features_always_include_target_temperature(
    hass: HomeAssistant,
) -> None:
    """Test target temperature is always offered, since every mode's frame carries it."""
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["supported_features"] == (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
    )


@pytest.mark.parametrize(
    ("restored_state", "restored_attributes", "expected"),
    [
        pytest.param(
            HVACMode.COOL,
            {"fan_mode": FAN_HIGH, "temperature": 29.0},
            (HVACMode.COOL, FAN_HIGH, 29.0),
            id="full_state",
        ),
        pytest.param(
            STATE_UNAVAILABLE,
            {},
            (HVACMode.OFF, FAN_AUTO, float(MIN_TEMP)),
            id="unavailable_falls_back_to_defaults",
        ),
        pytest.param(
            HVACMode.HEAT,
            {"fan_mode": FAN_HIGH, "temperature": 29.0},
            (HVACMode.OFF, FAN_HIGH, 29.0),
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
    expected: tuple[HVACMode, str, float],
) -> None:
    """Test the assumed state is restored, since infrared cannot read it back."""
    mock_restore_cache(
        hass, [State(_CLIMATE_ENTITY_ID, restored_state, restored_attributes)]
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.onida_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    expected_mode, expected_fan, expected_temp = expected
    assert state.state == expected_mode
    assert state.attributes["fan_mode"] == expected_fan
    assert state.attributes["temperature"] == expected_temp


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test set_temperature switches mode when one is given, even while off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
            ATTR_TEMPERATURE: 24,
            "hvac_mode": HVACMode.COOL,
        },
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == OnidaAcCommand(
            mode=OnidaAcMode.COOL, temperature=24, fan=OnidaAcFanSpeed.AUTO
        ).get_raw_timings()
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes["temperature"] == 24.0


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_unsupported_hvac_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test a mode the unit does not support is rejected instead of sent."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
                ATTR_TEMPERATURE: 24,
                "hvac_mode": HVACMode.HEAT,
            },
            blocking=True,
        )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0
