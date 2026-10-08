"""Tests for the Gree Infrared climate platform."""

import asyncio
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.gree_ac import (
    MAX_TEMP_F,
    MIN_TEMP,
    MIN_TEMP_F,
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcMode,
    GreeAcModel,
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
from homeassistant.components.gree_infrared.const import CONF_HVAC_MODES, MODEL_YAP1F
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_MODEL,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from tests.components.common import assert_availability_follows_source_entity
from tests.components.infrared import EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID
from tests.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)

_CLIMATE_ENTITY_ID = "climate.gree_ac"


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to set up."""
    return [Platform.CLIMATE]


@pytest.fixture
def has_receiver() -> bool:
    """Return whether the config entry has an infrared receiver configured."""
    return False


@pytest.fixture
def extra_entry_data(
    hvac_modes: list[HVACMode], request: pytest.FixtureRequest
) -> dict[str, Any]:
    """Return configured entry data, honoring tests that select a model."""
    return getattr(request, "param", {CONF_HVAC_MODES: hvac_modes})


@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity state and registry snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("has_receiver", "source_entity_ids"),
    [
        pytest.param(False, [EMITTER_ENTITY_ID], id="emitter"),
        pytest.param(
            True, [EMITTER_ENTITY_ID, RECEIVER_ENTITY_ID], id="emitter_and_receiver"
        ),
    ],
)
@pytest.mark.usefixtures("init_integration", "mock_infrared_emitter_entity")
async def test_availability_follows_sources(
    hass: HomeAssistant,
    source_entity_ids: list[str],
) -> None:
    """Test climate entity availability follows all configured infrared entities."""
    await assert_availability_follows_source_entity(
        hass, _CLIMATE_ENTITY_ID, source_entity_ids
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize(
    "unavailable_entity_id",
    [
        pytest.param(EMITTER_ENTITY_ID, id="emitter"),
        pytest.param(RECEIVER_ENTITY_ID, id="receiver"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_initial_availability_requires_emitter_and_receiver(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    unavailable_entity_id: str,
) -> None:
    """Test the entity starts unavailable if either emitter or receiver is."""
    hass.states.async_set(unavailable_entity_id, STATE_UNAVAILABLE)
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


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
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.COOL,
            temperature=MIN_TEMP,
            fan=GreeAcFanSpeed.AUTO,
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_failed_send_does_not_become_the_last_active_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test a mode whose frame never went out is not carried by a later off frame.

    The unit only reaches a mode if its frame was actually transmitted, so a send that
    raised must leave the remembered mode alone; otherwise the next off frame carries a
    mode the unit was never put into.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    with (
        patch.object(
            mock_infrared_emitter_entity,
            "async_send_command",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
            blocking=True,
        )

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
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.DRY,
            temperature=MIN_TEMP,
            fan=GreeAcFanSpeed.AUTO,
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_hvac_mode_off_keeps_the_last_active_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test a power-off frame carries the mode that was last active.

    The mode field is part of every frame and the entity's own mode is off by then, so
    the last active mode has to be tracked separately; dry here is deliberately not the
    first configured mode, which is what an untracked implementation would fall back to.
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
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.DRY,
            temperature=MIN_TEMP,
            fan=GreeAcFanSpeed.AUTO,
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
            GreeAcCommand(
                mode=GreeAcMode.COOL, temperature=24, fan=GreeAcFanSpeed.AUTO
            ),
            id="cool_24_auto",
        ),
        pytest.param(
            HVACMode.COOL,
            18,
            FAN_LOW,
            GreeAcCommand(mode=GreeAcMode.COOL, temperature=18, fan=GreeAcFanSpeed.LOW),
            id="cool_18_low",
        ),
        pytest.param(
            HVACMode.COOL,
            30,
            FAN_HIGH,
            GreeAcCommand(
                mode=GreeAcMode.COOL, temperature=30, fan=GreeAcFanSpeed.HIGH
            ),
            id="cool_30_high",
        ),
        pytest.param(
            HVACMode.DRY,
            24,
            FAN_MEDIUM,
            GreeAcCommand(
                mode=GreeAcMode.DRY, temperature=24, fan=GreeAcFanSpeed.MEDIUM
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
    expected_cmd: GreeAcCommand,
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
            GreeAcCommand(
                mode=GreeAcMode.HEAT, temperature=MIN_TEMP, fan=GreeAcFanSpeed.AUTO
            ),
            id="heat",
        ),
        pytest.param(
            HVACMode.FAN_ONLY,
            GreeAcCommand(
                mode=GreeAcMode.FAN_ONLY,
                temperature=MIN_TEMP,
                fan=GreeAcFanSpeed.AUTO,
            ),
            id="fan_only",
        ),
        pytest.param(
            HVACMode.AUTO,
            GreeAcCommand(
                mode=GreeAcMode.AUTO, temperature=MIN_TEMP, fan=GreeAcFanSpeed.AUTO
            ),
            id="auto",
        ),
    ],
)
async def test_set_hvac_mode_from_off_uses_defaults(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    expected_cmd: GreeAcCommand,
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
        == GreeAcCommand(
            mode=GreeAcMode.COOL, temperature=26, fan=GreeAcFanSpeed.AUTO
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
        == GreeAcCommand(
            mode=GreeAcMode.DRY, temperature=25, fan=GreeAcFanSpeed.AUTO
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
        == GreeAcCommand(
            mode=GreeAcMode.COOL, temperature=MIN_TEMP, fan=GreeAcFanSpeed.HIGH
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
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_received_fahrenheit_setpoint_survives_commands(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """A decoded Fahrenheit setpoint survives later commands until the user acts."""
    for temperature in range(MIN_TEMP_F, MAX_TEMP_F + 1):
        timings = GreeAcCommand(
            model=GreeAcModel.YAP1F,
            mode=GreeAcMode.COOL,
            temperature=temperature,
            fahrenheit=True,
        ).get_raw_timings()
        received = GreeAcCommand.from_raw_timings(timings, model=GreeAcModel.YAP1F)
        assert received is not None
        mock_infrared_receiver_entity._handle_received_signal(
            InfraredReceivedSignal(timings=timings)
        )
        await hass.async_block_till_done()
        mock_infrared_emitter_entity.send_command_calls.clear()

        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {
                ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
                "fan_mode": FAN_LOW if temperature % 2 else FAN_HIGH,
            },
            blocking=True,
        )

        assert len(mock_infrared_emitter_entity.send_command_calls) == 1
        command = mock_infrared_emitter_entity.send_command_calls[0]
        assert command.fahrenheit is True
        assert command.temperature == received.temperature

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=GreeAcModel.YAP1F,
                mode=GreeAcMode.COOL,
                temperature=74,
                fahrenheit=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    mock_infrared_emitter_entity.send_command_calls.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 24},
        blocking=True,
    )
    assert mock_infrared_emitter_entity.send_command_calls[0].temperature == 75

    # The explicit target change dropped the wire value: a later command converts
    # from the Celsius target instead of reviving the received 74 °F.
    mock_infrared_emitter_entity.send_command_calls.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_LOW},
        blocking=True,
    )
    assert mock_infrared_emitter_entity.send_command_calls[0].temperature == 75

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=GreeAcModel.YAP1F,
                mode=GreeAcMode.COOL,
                temperature=74,
                fahrenheit=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=GreeAcModel.YAP1F,
                mode=GreeAcMode.COOL,
                temperature=24,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    mock_infrared_emitter_entity.send_command_calls.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_LOW},
        blocking=True,
    )
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert (command.temperature, command.fahrenheit) == (24, False)

    # The Celsius frame dropped the wire value too: re-selecting the scale
    # converts the Celsius target instead of reviving the received 74 °F.
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    mock_infrared_emitter_entity.send_command_calls.clear()
    await climate.async_set_fahrenheit(True)
    assert mock_infrared_emitter_entity.send_command_calls[0].temperature == 75


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_changing_fahrenheit_scale_drops_received_wire_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Changing scale must convert the current target, not revive receiver data."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=GreeAcModel.YAP1F,
                mode=GreeAcMode.COOL,
                temperature=74,
                fahrenheit=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    mock_infrared_emitter_entity.send_command_calls.clear()

    await climate.async_set_fahrenheit(False)
    await climate.async_set_fahrenheit(True)

    assert mock_infrared_emitter_entity.send_command_calls[-1].temperature == 73


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.DRY], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_failed_scale_change_restores_received_wire_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """A failed scale send restores the received wire setpoint."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=GreeAcModel.YAP1F,
                mode=GreeAcMode.COOL,
                temperature=74,
                fahrenheit=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None

    with (
        patch.object(
            mock_infrared_emitter_entity,
            "async_send_command",
            side_effect=RuntimeError("send failed"),
        ),
        pytest.raises(RuntimeError, match="send failed"),
    ):
        await climate.async_set_fahrenheit(False)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_LOW},
        blocking=True,
    )
    command = mock_infrared_emitter_entity.send_command_calls[-1]
    assert (command.temperature, command.fahrenheit) == (74, True)


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_timer_set_while_off_sends_off_state_timer_frame(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A timer set while off is sent in a power-off frame."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.OFF)
    previous_send_count = len(mock_infrared_emitter_entity.send_command_calls)

    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: "number.gree_ac_timer", "value": 0.5},
        blocking=True,
    )

    assert (
        len(mock_infrared_emitter_entity.send_command_calls) == previous_send_count + 1
    )
    command = GreeAcCommand.from_raw_timings(
        mock_infrared_emitter_entity.send_command_calls[-1].get_raw_timings(),
        model=GreeAcModel.YAP1F,
    )
    assert command is not None
    assert not command.power
    assert command.timer_hours == 0.5
    state = hass.states.get("number.gree_ac_timer")
    assert state is not None
    assert state.state == "0.5"


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_mode_off_preserves_active_timer_frame(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A power-off frame retains the active timer setting."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await climate.async_set_timer_hours(1.0)
    previous_deadline = climate._timer_deadline

    await climate.async_set_hvac_mode(HVACMode.OFF)

    command = GreeAcCommand.from_raw_timings(
        mock_infrared_emitter_entity.send_command_calls[-1].get_raw_timings(),
        model=GreeAcModel.YAP1F,
    )
    assert command is not None
    assert not command.power
    assert command.timer_hours == 1.0
    assert previous_deadline is not None
    assert climate._timer_deadline is not None
    assert climate._timer_deadline >= previous_deadline
    assert climate._timer_deadline - previous_deadline < timedelta(seconds=1)
    state = hass.states.get("number.gree_ac_timer")
    assert state is not None
    assert state.state == "1.0"


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_failed_timer_send_reschedules_previous_expiry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed timer replacement leaves the previous expiry scheduled."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await climate.async_set_timer_hours(0.5)
    previous_deadline = climate._timer_deadline
    assert previous_deadline is not None
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_send(command: Any) -> None:
        started.set()
        await release.wait()
        raise HomeAssistantError("send failed")

    with patch.object(mock_infrared_emitter_entity, "async_send_command", blocked_send):
        timer_task = hass.async_create_task(climate.async_set_timer_hours(1.0))
        await started.wait()
        freezer.move_to(previous_deadline)
        async_fire_time_changed(hass)
        release.set()
        with pytest.raises(HomeAssistantError):
            await timer_task

    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("number.gree_ac_timer")
    assert state is not None
    assert state.state == "0.0"


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_timer_number_updates_after_full_state_send(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The number entity reflects a timer re-encoded by a full-state send."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await climate.async_set_timer_hours(2.0)

    freezer.move_to(freezer() + timedelta(hours=1))
    await climate.async_set_fan_mode(FAN_AUTO)

    assert climate._state.timer_hours == 1.0
    state = hass.states.get("number.gree_ac_timer")
    assert state is not None
    assert state.state == "1.0"


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_task_is_cancelled_on_entry_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """A pending received-signal update ends when its config entry unloads."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate._state.command_lock.acquire()
    try:
        mock_infrared_receiver_entity._handle_received_signal(
            InfraredReceivedSignal(
                timings=GreeAcCommand(
                    mode=GreeAcMode.COOL, temperature=24
                ).get_raw_timings()
            )
        )
        await asyncio.sleep(0)
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    finally:
        climate._state.command_lock.release()

    await hass.async_block_till_done()
    assert climate._attr_hvac_mode is HVACMode.OFF


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_timer_expiry_updates_number_without_another_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The timer entity turns off when its deadline passes without a command."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_timer_hours(0.5)
    entity_id = "number.gree_ac_timer"
    assert hass.states.get(entity_id).state == "0.5"

    freezer.move_to(freezer() + timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "0.0"


@pytest.mark.usefixtures("init_integration")
async def test_timer_deadline_matches_quantized_duration_after_state_send(
    mock_config_entry: MockConfigEntry, freezer: FrozenDateTimeFactory
) -> None:
    """A full-state send restarts the local timer at its encoded duration."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await climate.async_set_timer_hours(0.5)
    previous_deadline = climate._timer_deadline

    freezer.move_to(freezer() + timedelta(minutes=20))
    await climate.async_set_fan_mode(FAN_LOW)

    assert climate._timer_deadline == previous_deadline + timedelta(minutes=20)


@pytest.mark.usefixtures("init_integration")
async def test_failed_state_send_keeps_timer_deadline(
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed full-state send does not change the existing timer deadline."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await climate.async_set_timer_hours(0.5)
    freezer.move_to(freezer() + timedelta(minutes=20))
    previous_deadline = climate._timer_deadline

    with (
        patch.object(
            mock_infrared_emitter_entity,
            "async_send_command",
            side_effect=HomeAssistantError,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await climate.async_set_fan_mode(FAN_LOW)

    assert climate._timer_deadline == previous_deadline


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_expired_restored_timer_starts_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    platforms: list[Platform],
) -> None:
    """A restored timer whose deadline passed is cleared during setup."""
    freezer.move_to("2024-01-01 12:00:00+00:00")
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(_CLIMATE_ENTITY_ID, HVACMode.OFF, {ATTR_TEMPERATURE: 24.0}),
                {
                    "last_active_hvac_mode": HVACMode.COOL.value,
                    "timer_hours": 0.5,
                    "timer_deadline": "2024-01-01T11:30:00+00:00",
                },
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.gree_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("number.gree_ac_timer").state == "0.0"


@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_option_validation_uses_mode_after_waiting_for_command_lock(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """An option queued behind a mode change validates against the new mode."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_send(command: Any) -> None:
        started.set()
        await release.wait()

    with patch.object(mock_infrared_emitter_entity, "async_send_command", blocked_send):
        mode_task = hass.async_create_task(climate.async_set_hvac_mode(HVACMode.HEAT))
        await started.wait()
        option_task = hass.async_create_task(climate.async_set_option("econo", True))
        await asyncio.sleep(0)
        release.set()
        await mode_task
        with pytest.raises(ServiceValidationError) as err:
            await option_task
        assert err.value.translation_key == "econo_not_available"

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1


@pytest.mark.parametrize(
    ("option", "mode", "translation_key"),
    [
        ("sleep", HVACMode.AUTO, "sleep_not_available"),
        ("econo", HVACMode.HEAT, "econo_not_available"),
        ("absence", HVACMode.COOL, "absence_not_available"),
    ],
)
@pytest.mark.parametrize(
    "extra_entry_data",
    [
        {
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO],
            CONF_MODEL: MODEL_YAP1F,
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_option_mode_errors_have_translation_keys(
    mock_config_entry: MockConfigEntry,
    option: str,
    mode: HVACMode,
    translation_key: str,
) -> None:
    """Mode-specific option validation errors identify their translations."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(mode)

    with pytest.raises(ServiceValidationError) as err:
        await climate.async_set_option(option, True)

    assert err.value.translation_key == translation_key


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_receiver_off_timer_frame_schedules_expiry(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A received off-state timer frame updates and expires the number value."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=GreeAcModel.YAP1F,
                power=False,
                mode=GreeAcMode.COOL,
                temperature=24,
                timer_hours=0.5,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get("number.gree_ac_timer")
    assert state is not None
    assert state.state == "0.5"
    freezer.move_to(freezer() + timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("number.gree_ac_timer")
    assert state is not None
    assert state.state == "0.0"


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("lib_fan", "expected_fan_mode"),
    [
        pytest.param(GreeAcFanSpeed.AUTO, FAN_AUTO, id="auto"),
        pytest.param(GreeAcFanSpeed.LOW, FAN_LOW, id="low"),
        pytest.param(GreeAcFanSpeed.MEDIUM, FAN_MEDIUM, id="medium"),
        pytest.param(GreeAcFanSpeed.HIGH, FAN_HIGH, id="high"),
    ],
)
async def test_receiver_updates_state_on_cool_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    lib_fan: GreeAcFanSpeed,
    expected_fan_mode: str,
) -> None:
    """Test that a received cool signal updates mode, temperature and every fan speed."""
    timings = GreeAcCommand(
        mode=GreeAcMode.COOL, temperature=24, fan=lib_fan
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
async def test_receiver_waits_for_in_flight_command(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A received frame updates state only after an outbound send releases the lock."""
    started = asyncio.Event()
    release = asyncio.Event()

    async def blocked_send(command: Any) -> None:
        started.set()
        await release.wait()

    with patch.object(mock_infrared_emitter_entity, "async_send_command", blocked_send):
        send_task = hass.async_create_task(
            hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_HVAC_MODE,
                {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
                blocking=True,
            )
        )
        await started.wait()
        mock_infrared_receiver_entity._handle_received_signal(
            InfraredReceivedSignal(
                timings=GreeAcCommand(
                    mode=GreeAcMode.DRY, temperature=28
                ).get_raw_timings()
            )
        )
        await asyncio.sleep(0)
        state = hass.states.get(_CLIMATE_ENTITY_ID)
        assert state is not None
        assert state.state == HVACMode.OFF

        release.set()
        await send_task
        await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.DRY


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_updates_state_on_off_signal(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a received off signal sets mode to off, preserving temperature and fan."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.COOL, temperature=24, fan=GreeAcFanSpeed.MEDIUM
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=24,
                fan=GreeAcFanSpeed.MEDIUM,
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
async def test_set_hvac_mode_off_keeps_the_mode_seen_by_the_receiver(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a power-off frame carries the last mode the physical remote selected."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.DRY, temperature=24, fan=GreeAcFanSpeed.MEDIUM
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

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
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.DRY,
            temperature=24,
            fan=GreeAcFanSpeed.MEDIUM,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_off_signal_records_the_mode_it_carries(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test an off frame seen before any on frame still records the mode it carries."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                power=False,
                mode=GreeAcMode.DRY,
                temperature=24,
                fan=GreeAcFanSpeed.MEDIUM,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

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
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.DRY,
            temperature=24,
            fan=GreeAcFanSpeed.MEDIUM,
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_last_active_mode_restored_on_restart_while_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
) -> None:
    """Test an off frame after a restart carries the mode the unit was last in.

    The visible state only records off, so without the extra restore data the off
    frame would fall back to the first configured mode instead of the real one.
    """
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(_CLIMATE_ENTITY_ID, HVACMode.OFF, {ATTR_TEMPERATURE: 24.0}),
                {"last_active_hvac_mode": HVACMode.DRY.value},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.gree_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

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
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.DRY,
            temperature=24,
            fan=GreeAcFanSpeed.AUTO,
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_last_active_mode_restored_from_unavailable_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
) -> None:
    """Test the last active mode survives a restart from an unavailable state.

    The visible state carries nothing usable once it is unavailable, so the extra
    restore data has to be read regardless of what the visible state says.
    """
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(_CLIMATE_ENTITY_ID, STATE_UNAVAILABLE),
                {"last_active_hvac_mode": HVACMode.DRY.value},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.gree_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

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
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.DRY,
            temperature=MIN_TEMP,
            fan=GreeAcFanSpeed.AUTO,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_ignores_unconfigured_hvac_mode(
    hass: HomeAssistant,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a signal for a mode the user did not configure does not change state."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.HEAT, temperature=24, fan=GreeAcFanSpeed.HIGH
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
async def test_receiver_ignores_non_gree_ac_signal(
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
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
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
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_state_restored_on_restart(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
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

    with patch("homeassistant.components.gree_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    expected_mode, expected_fan, expected_temp = expected
    assert state.state == expected_mode
    assert state.attributes["fan_mode"] == expected_fan
    assert state.attributes["temperature"] == expected_temp


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "expected_cmd"),
    [
        pytest.param(
            HVACMode.COOL,
            GreeAcCommand(
                mode=GreeAcMode.COOL, temperature=24, fan=GreeAcFanSpeed.AUTO
            ),
            id="cool",
        ),
        pytest.param(
            HVACMode.OFF,
            GreeAcCommand(
                power=False,
                mode=GreeAcMode.COOL,
                temperature=24,
                fan=GreeAcFanSpeed.AUTO,
            ),
            id="off",
        ),
    ],
)
async def test_set_temperature_with_hvac_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    hvac_mode: HVACMode,
    expected_cmd: GreeAcCommand,
) -> None:
    """Test set_temperature applies a given mode, off included, while off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
            ATTR_TEMPERATURE: 24,
            "hvac_mode": hvac_mode,
        },
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert timings == expected_cmd.get_raw_timings()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == hvac_mode
    assert state.attributes["temperature"] == 24.0


async def test_fahrenheit_temperatures_round_trip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
) -> None:
    """Test temperatures convert to Celsius on a Fahrenheit installation."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_restore_cache(
        hass,
        [
            State(
                _CLIMATE_ENTITY_ID,
                HVACMode.COOL,
                {"fan_mode": FAN_AUTO, "temperature": 75},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.gree_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["temperature"] == 75

    mock_infrared_emitter_entity.send_command_calls.clear()
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 75},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            mode=GreeAcMode.COOL, temperature=24, fan=GreeAcFanSpeed.AUTO
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_set_temperature_with_hvac_mode_off_while_active(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test requesting off alongside a temperature turns an active AC off."""
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
        {
            ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
            ATTR_TEMPERATURE: 26,
            "hvac_mode": HVACMode.OFF,
        },
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.COOL,
            temperature=26,
            fan=GreeAcFanSpeed.AUTO,
        ).get_raw_timings()
    )

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert state.attributes["temperature"] == 26.0


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
