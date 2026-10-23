"""Tests for the Gree Infrared climate platform."""

import asyncio
import contextlib
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
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_restore_state_shutdown_restart,
    mock_restore_cache,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from pytest_homeassistant.components.common import (
    assert_availability_follows_source_entity,
)
from pytest_homeassistant.components.infrared import (
    EMITTER_ENTITY_ID,
    RECEIVER_ENTITY_ID,
)
from pytest_homeassistant.components.infrared.common import (
    MockInfraredEmitterEntity,
    MockInfraredReceiverEntity,
)
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
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.gree_infrared.const import CONF_HVAC_MODES, MODEL_YAP1F
from homeassistant.components.gree_infrared.state import COALESCE_DELAY_SEC
from homeassistant.components.infrared import InfraredReceivedSignal
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_MODEL,
    STATE_UNAVAILABLE,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import STORAGE_KEY as RESTORE_STATE_KEY
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

_CLIMATE_ENTITY_ID = "climate.gree_ac"
_STORED_CLIMATE_DATA = {
    "native_current_temperature": None,
    "native_target_temperature": 25.0,
    "native_target_temperature_high": None,
    "native_target_temperature_low": None,
    "native_temperature_unit": UnitOfTemperature.CELSIUS.value,
}


async def _flush_coalesced(hass: HomeAssistant) -> None:
    """Wait out the coalescing window, then drain the flush task."""
    await asyncio.sleep(COALESCE_DELAY_SEC + 0.2)
    await hass.async_block_till_done()


async def _flush_now(hass: HomeAssistant, climate) -> None:
    """Flush staged state immediately (freezer-safe: no real sleep).

    Cancels the pending coalesce timer, then runs the flush coroutine
    directly. Used by tests that freeze time, where loop.call_later-based
    windows never expire on their own.
    """
    handle = climate._state._coalesce_handle
    climate._state._coalesce_handle = None
    if handle is not None:
        handle.cancel()
    if not climate._state.coalesce_dirty:
        await hass.async_block_till_done()
        return
    await climate._async_flush_coalesced()
    await hass.async_block_till_done()


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
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)
    mock_infrared_emitter_entity.send_command_calls.clear()

    with patch.object(
        mock_infrared_emitter_entity,
        "async_send_command",
        side_effect=HomeAssistantError,
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
            blocking=True,
        )
        await _flush_coalesced(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )
    await _flush_coalesced(hass)

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
    ("prior_modes", "service", "power", "expected_state"),
    [
        pytest.param(
            (HVACMode.DRY,), SERVICE_TURN_OFF, False, HVACMode.OFF, id="turn_off"
        ),
        pytest.param(
            (HVACMode.DRY, HVACMode.OFF),
            SERVICE_TURN_ON,
            True,
            HVACMode.DRY,
            id="turn_on",
        ),
    ],
)
async def test_turn_on_off_uses_the_last_active_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    prior_modes: tuple[HVACMode, ...],
    service: str,
    power: bool,
    expected_state: HVACMode,
) -> None:
    """Test turning on or off sends a frame carrying the last active mode.

    Dry is deliberately not the first configured mode, so a turn on that ignored the
    last active mode would come back in cool.
    """
    for hvac_mode in prior_modes:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": hvac_mode},
            blocking=True,
        )
        await _flush_coalesced(hass)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID},
        blocking=True,
    )
    await _flush_coalesced(hass)

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            power=power,
            mode=GreeAcMode.DRY,
            temperature=MIN_TEMP,
            fan=GreeAcFanSpeed.AUTO,
        ).get_raw_timings()
    )
    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == expected_state


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
    await _flush_coalesced(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": fan},
        blocking=True,
    )
    await _flush_coalesced(hass)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": hvac_mode},
        blocking=True,
    )
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 26},
        blocking=True,
    )
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 25},
        blocking=True,
    )
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)
    mock_infrared_emitter_entity.send_command_calls.clear()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_HIGH},
        blocking=True,
    )
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)

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
        await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)
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
    await _flush_coalesced(hass)
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
    await _flush_coalesced(hass)
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert (command.temperature, command.fahrenheit) == (24, False)

    # The Celsius frame dropped the wire value too: re-selecting the scale
    # converts the Celsius target instead of reviving the received 74 °F.
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    mock_infrared_emitter_entity.send_command_calls.clear()
    await climate.async_set_fahrenheit(True)
    await _flush_coalesced(hass)
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
    await _flush_coalesced(hass)
    await climate.async_set_fahrenheit(True)
    await _flush_coalesced(hass)

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
    """A failed scale send keeps the staged scale; the next flush sends it."""
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

    with patch.object(
        mock_infrared_emitter_entity,
        "async_send_command",
        side_effect=HomeAssistantError("send failed"),
    ):
        await climate.async_set_fahrenheit(False)
        await _flush_coalesced(hass)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "fan_mode": FAN_LOW},
        blocking=True,
    )
    await _flush_coalesced(hass)
    command = mock_infrared_emitter_entity.send_command_calls[-1]
    assert (command.temperature, command.fahrenheit) == (23, False)


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
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)
    await climate.async_set_timer_hours(1.0)
    await _flush_now(hass, climate)
    previous_deadline = climate._timer_deadline

    await climate.async_set_hvac_mode(HVACMode.OFF)
    await _flush_coalesced(hass)

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
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    previous_deadline = climate._timer_deadline
    assert previous_deadline is not None

    def failed_send(command: Any) -> None:
        raise HomeAssistantError("send failed")

    with patch.object(mock_infrared_emitter_entity, "async_send_command", failed_send):
        await climate.async_set_timer_hours(1.0)
        await _flush_now(hass, climate)

    freezer.move_to(previous_deadline)
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
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(2.0)
    await _flush_now(hass, climate)

    freezer.move_to(freezer() + timedelta(hours=1))
    await climate.async_set_fan_mode(FAN_AUTO)
    await _flush_now(hass, climate)

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
    await _flush_now(hass, climate)
    entity_id = "number.gree_ac_timer"
    assert hass.states.get(entity_id).state == "0.5"

    freezer.move_to(freezer() + timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "0.0"


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize("hvac_modes", [[HVACMode.COOL, HVACMode.HEAT]])
@pytest.mark.usefixtures("init_integration")
async def test_turn_on_uses_remote_mode_received_while_waiting(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Turning on preserves a remote mode queued ahead of the command."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_coalesced(hass)
    await climate._state.command_lock.acquire()
    try:
        mock_infrared_receiver_entity._handle_received_signal(
            InfraredReceivedSignal(
                timings=GreeAcCommand(
                    mode=GreeAcMode.HEAT, power=False, temperature=24
                ).get_raw_timings()
            )
        )
        await asyncio.sleep(0)
        turn_on_task = hass.async_create_task(climate.async_turn_on())
        await asyncio.sleep(0)
    finally:
        climate._state.command_lock.release()
    await turn_on_task
    await hass.async_block_till_done()
    await _flush_coalesced(hass)

    command = GreeAcCommand.from_raw_timings(
        mock_infrared_emitter_entity.send_command_calls[-1].get_raw_timings()
    )
    assert command is not None
    assert command.power
    assert command.mode is GreeAcMode.HEAT
    assert hass.states.get(_CLIMATE_ENTITY_ID).state == HVACMode.HEAT


@pytest.mark.parametrize(
    "platforms", [[Platform.CLIMATE, Platform.NUMBER, Platform.SWITCH]]
)
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_timer_expiry_during_failed_option_send(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed option send keeps the staged option; expiry still clears the timer."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    deadline = climate._timer_deadline
    assert deadline is not None

    def failed_send(command: Any) -> None:
        raise HomeAssistantError("send failed")

    with patch.object(mock_infrared_emitter_entity, "async_send_command", failed_send):
        await climate.async_set_option("turbo", True)
        freezer.move_to(deadline)
        async_fire_time_changed(hass)
        await _flush_now(hass, climate)

    await hass.async_block_till_done()
    assert climate._state.turbo
    assert hass.states.get("switch.gree_ac_turbo").state == "on"
    assert hass.states.get("number.gree_ac_timer").state == "0.0"


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_failed_mode_send_does_not_suppress_timer_expiry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed mode retry cannot prevent the committed timer from switching off."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    deadline = climate._timer_deadline
    assert deadline is not None

    with patch.object(
        mock_infrared_emitter_entity,
        "async_send_command",
        side_effect=HomeAssistantError("send failed"),
    ):
        await climate.async_set_hvac_mode(HVACMode.COOL)
        await _flush_now(hass, climate)

    assert not climate._state.pending_power_change
    freezer.move_to(deadline)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_CLIMATE_ENTITY_ID).state == HVACMode.OFF


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_failed_off_send_does_not_reverse_timer_expiry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed OFF send cannot make an existing ON timer power the unit back on."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    deadline = climate._timer_deadline
    assert deadline is not None

    with patch.object(
        mock_infrared_emitter_entity,
        "async_send_command",
        side_effect=HomeAssistantError("send failed"),
    ):
        await climate.async_set_hvac_mode(HVACMode.OFF)
        await _flush_now(hass, climate)

    freezer.move_to(deadline)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_CLIMATE_ENTITY_ID).state == HVACMode.OFF


@pytest.mark.usefixtures("init_integration")
async def test_timer_deadline_matches_quantized_duration_after_state_send(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A full-state send restarts the local timer at its encoded duration."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    previous_deadline = climate._timer_deadline

    freezer.move_to(freezer() + timedelta(minutes=20))
    await climate.async_set_fan_mode(FAN_LOW)
    await _flush_now(hass, climate)

    assert climate._timer_deadline == previous_deadline + timedelta(minutes=20)


@pytest.mark.usefixtures("init_integration")
async def test_failed_state_send_keeps_timer_deadline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed full-state send does not change the existing timer deadline."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    freezer.move_to(freezer() + timedelta(minutes=20))
    previous_deadline = climate._timer_deadline

    with patch.object(
        mock_infrared_emitter_entity,
        "async_send_command",
        side_effect=HomeAssistantError,
    ):
        await climate.async_set_fan_mode(FAN_LOW)
        await _flush_now(hass, climate)

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
                    **_STORED_CLIMATE_DATA,
                    "native_target_temperature": 24.0,
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


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.parametrize(
    ("restored_hvac_mode", "expected_hvac_mode"),
    [
        # Off-timer: the unit was on in COOL and the timer turned it off while stopped.
        (HVACMode.COOL, HVACMode.OFF),
        # On-timer: the unit was off and the timer turned it on while stopped.
        (HVACMode.OFF, HVACMode.COOL),
    ],
)
async def test_expired_restored_timer_applies_power_without_send(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
    platforms: list[Platform],
    restored_hvac_mode: HVACMode,
    expected_hvac_mode: HVACMode,
) -> None:
    """A restored timer that expired while stopped flips power without a frame."""
    freezer.move_to("2024-01-01 12:00:00+00:00")
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(_CLIMATE_ENTITY_ID, restored_hvac_mode, {ATTR_TEMPERATURE: 24.0}),
                {
                    **_STORED_CLIMATE_DATA,
                    "native_target_temperature": 24.0,
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

    assert hass.states.get(_CLIMATE_ENTITY_ID).state == expected_hvac_mode
    assert hass.states.get("number.gree_ac_timer").state == "0.0"
    assert len(mock_infrared_emitter_entity.send_command_calls) == 0


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
    """An option staged after a mode change validates against the new mode."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await climate.async_set_hvac_mode(HVACMode.HEAT)
    with pytest.raises(ServiceValidationError) as err:
        await climate.async_set_option("econo", True)
    assert err.value.translation_key == "econo_not_available"
    await _flush_coalesced(hass)

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
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    option: str,
    mode: HVACMode,
    translation_key: str,
) -> None:
    """Mode-specific option validation errors identify their translations."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(mode)
    await _flush_coalesced(hass)

    with pytest.raises(ServiceValidationError) as err:
        await climate.async_set_option(option, True)

    await _flush_coalesced(hass)

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
        assert state.state == HVACMode.COOL

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
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)

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


@pytest.mark.parametrize(
    ("extra_data", "expected_temperature"),
    [
        pytest.param(
            {"last_active_hvac_mode": HVACMode.DRY.value},
            24,
            id="legacy_extra_data_falls_back_to_attributes",
        ),
        pytest.param(
            {**_STORED_CLIMATE_DATA, "last_active_hvac_mode": HVACMode.DRY.value},
            25,
            id="climate_extra_data",
        ),
    ],
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_last_active_mode_restored_on_restart_while_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    extra_data: dict[str, Any],
    expected_temperature: int,
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
                extra_data,
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
    await _flush_coalesced(hass)

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            power=False,
            mode=GreeAcMode.DRY,
            temperature=expected_temperature,
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
    await _flush_coalesced(hass)

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
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.SWING_HORIZONTAL_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )


@pytest.mark.parametrize(
    ("restored_state", "restored_attributes", "expected"),
    [
        pytest.param(
            HVACMode.COOL,
            {
                "fan_mode": FAN_HIGH,
                "temperature": 29.0,
                "temperature_unit": UnitOfTemperature.CELSIUS,
            },
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
            {
                "fan_mode": FAN_HIGH,
                "temperature": 29.0,
                "temperature_unit": UnitOfTemperature.CELSIUS,
            },
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


@pytest.mark.parametrize(
    ("restored_attributes", "unit_system", "expected_temperature"),
    [
        pytest.param(
            {"temperature": 17, "temperature_unit": UnitOfTemperature.CELSIUS},
            METRIC_SYSTEM,
            17,
            id="celsius_to_celsius",
        ),
        pytest.param(
            {"temperature": 17, "temperature_unit": UnitOfTemperature.CELSIUS},
            US_CUSTOMARY_SYSTEM,
            63,
            id="celsius_to_fahrenheit",
        ),
        pytest.param(
            {"temperature": 63, "temperature_unit": UnitOfTemperature.FAHRENHEIT},
            METRIC_SYSTEM,
            17,
            id="fahrenheit_to_celsius",
        ),
        pytest.param(
            {"temperature": 63, "temperature_unit": UnitOfTemperature.FAHRENHEIT},
            US_CUSTOMARY_SYSTEM,
            63,
            id="fahrenheit_to_fahrenheit",
        ),
        pytest.param({"temperature": 17}, METRIC_SYSTEM, 17, id="legacy_celsius"),
        pytest.param(
            {"temperature": 63}, US_CUSTOMARY_SYSTEM, 63, id="legacy_fahrenheit"
        ),
    ],
)
async def test_restore_temperature_unit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    platforms: list[Platform],
    restored_attributes: dict[str, int | str],
    unit_system: UnitSystem,
    expected_temperature: int,
) -> None:
    """Test restoration uses the saved unit, falling back to the configured unit."""
    hass.config.units = unit_system
    mock_restore_cache(
        hass,
        [
            State(
                _CLIMATE_ENTITY_ID,
                HVACMode.COOL,
                restored_attributes,
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.gree_infrared.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.attributes["temperature"] == expected_temperature

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await _flush_coalesced(hass)

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    timings = mock_infrared_emitter_entity.send_command_calls[0].get_raw_timings()
    assert (
        timings
        == GreeAcCommand(
            mode=GreeAcMode.COOL, temperature=17, fan=GreeAcFanSpeed.AUTO
        ).get_raw_timings()
    )


@pytest.mark.usefixtures("init_integration")
async def test_restore_data_saved(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test the native temperatures are stored along with the last active mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID,
            ATTR_TEMPERATURE: 25,
            "hvac_mode": HVACMode.DRY,
        },
        blocking=True,
    )
    await _flush_coalesced(hass)

    await async_mock_restore_state_shutdown_restart(hass)

    stored = {
        data["state"]["entity_id"]: data["extra_data"]
        for data in hass_storage[RESTORE_STATE_KEY]["data"]
    }
    stored_climate_data = stored[_CLIMATE_ENTITY_ID]
    assert {
        key: stored_climate_data[key] for key in _STORED_CLIMATE_DATA
    } == _STORED_CLIMATE_DATA
    assert stored_climate_data["last_active_hvac_mode"] == HVACMode.DRY.value


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
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)

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
    await _flush_coalesced(hass)
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
    await _flush_coalesced(hass)

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

    await _flush_coalesced(hass)

    assert len(mock_infrared_emitter_entity.send_command_calls) == 0


@pytest.mark.parametrize(
    "extra_entry_data",
    [
        pytest.param(
            {
                CONF_MODEL: "generic",
                CONF_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY],
            },
            id="generic",
        ),
        pytest.param(
            {
                CONF_MODEL: MODEL_YAP1F,
                CONF_HVAC_MODES: [HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY],
            },
            id="yap1f",
        ),
    ],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_power_services_preserve_last_active_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Power on resumes cooling even when heating is configured first."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await _flush_coalesced(hass)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID},
        blocking=True,
    )
    await _flush_coalesced(hass)
    assert hass.states.get(_CLIMATE_ENTITY_ID).state == HVACMode.OFF
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID},
        blocking=True,
    )
    await _flush_coalesced(hass)
    assert hass.states.get(_CLIMATE_ENTITY_ID).state == HVACMode.COOL
    assert len(mock_infrared_emitter_entity.send_command_calls) == 3
    off_command = mock_infrared_emitter_entity.send_command_calls[1]
    on_command = mock_infrared_emitter_entity.send_command_calls[2]
    assert off_command.power is False
    assert on_command.power is True
    assert on_command.mode == GreeAcMode.COOL


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.parametrize(
    "extra_entry_data",
    [
        {
            CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT, HVACMode.DRY],
            CONF_MODEL: MODEL_YAP1F,
        }
    ],
    indirect=True,
)
@pytest.mark.parametrize("initial_mode", [GreeAcMode.COOL, GreeAcMode.HEAT])
@pytest.mark.parametrize(
    ("method", "args", "kwargs"),
    [
        pytest.param("async_set_option", ("turbo", True), {}, id="turbo"),
        pytest.param("async_set_option", ("light", False), {}, id="light"),
        pytest.param("async_set_option", ("sleep", False), {}, id="sleep"),
        pytest.param("async_set_option", ("ifeel", True), {}, id="ifeel"),
        pytest.param("async_set_fresh_air", ("level_1",), {}, id="fresh_air"),
        pytest.param("async_set_timer_hours", (1.0,), {}, id="timer"),
        pytest.param("async_set_swing_v_position", (2,), {}, id="vertical_vane"),
        pytest.param("async_set_swing_mode", ("on",), {}, id="vertical_swing"),
        pytest.param("async_set_swing_h_position", (3,), {}, id="horizontal_vane"),
        pytest.param(
            "async_set_swing_horizontal_mode", ("on",), {}, id="horizontal_swing"
        ),
        pytest.param(
            "async_set_hvac_mode", (HVACMode.DRY,), {}, id="mode_clears_flags"
        ),
        pytest.param(
            "async_set_temperature",
            (),
            {"temperature": 25, "hvac_mode": HVACMode.DRY},
            id="temperature_clears_flags",
        ),
        pytest.param(
            "async_set_temperature", (), {"temperature": 25}, id="temperature"
        ),
        pytest.param("async_set_fahrenheit", (False,), {}, id="scale"),
        pytest.param("async_set_display_temp", (3,), {}, id="display_temperature"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_cancelled_send_restores_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
    freezer: FrozenDateTimeFactory,
    initial_mode: GreeAcMode,
    method: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> None:
    """Cancellation retains options, wire setpoint and the existing timer expiry."""
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                model=GreeAcModel.YAP1F,
                mode=initial_mode,
                temperature=74,
                fahrenheit=True,
                sleep=True,
                econo=True,
                absence=True,
                timer_hours=0.5,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_fan_mode(FAN_LOW)
    await _flush_now(hass, climate)
    expected_frame = mock_infrared_emitter_entity.send_command_calls[
        -1
    ].get_raw_timings()
    previous_data = climate.extra_restore_state_data.as_dict()
    previous_attributes = dict(hass.states.get(_CLIMATE_ENTITY_ID).attributes)
    previous_deadline = climate._timer_deadline
    assert previous_deadline is not None
    started = asyncio.Event()

    async def blocked_send(command: GreeAcCommand) -> None:
        started.set()
        await asyncio.Event().wait()

    with patch.object(mock_infrared_emitter_entity, "async_send_command", blocked_send):
        await climate.async_set_fan_mode(FAN_LOW)
        flush_task = hass.async_create_task(_flush_now(hass, climate))
        await started.wait()
        task = hass.async_create_task(getattr(climate, method)(*args, **kwargs))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        flush_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await flush_task

    assert climate.extra_restore_state_data.as_dict() == previous_data
    assert climate._timer_deadline == previous_deadline
    assert dict(hass.states.get(_CLIMATE_ENTITY_ID).attributes) == previous_attributes

    # A later full-state send must not transmit any cancelled value.
    await climate.async_set_fan_mode(FAN_LOW)
    await _flush_now(hass, climate)
    assert (
        mock_infrared_emitter_entity.send_command_calls[-1].get_raw_timings()
        == expected_frame
    )
    assert mock_infrared_emitter_entity.send_command_calls[-1].temperature == 74
    sends = len(mock_infrared_emitter_entity.send_command_calls)
    freezer.move_to(previous_deadline)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("number.gree_ac_timer").state == "0.0"
    assert len(mock_infrared_emitter_entity.send_command_calls) == sends


@pytest.mark.parametrize(
    "platforms", [[Platform.CLIMATE, Platform.NUMBER, Platform.SELECT, Platform.SWITCH]]
)
@pytest.mark.parametrize(
    "extra_entry_data",
    [{CONF_HVAC_MODES: [HVACMode.COOL, HVACMode.HEAT], CONF_MODEL: MODEL_YAP1F}],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_climate_rename_preserves_sibling_controls(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Registry rename reattaches the owner used by all sibling control platforms."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_coalesced(hass)
    entity_registry.async_update_entity(
        _CLIMATE_ENTITY_ID, new_entity_id="climate.renamed_gree_ac"
    )
    await hass.async_block_till_done()
    assert hass.states.get(_CLIMATE_ENTITY_ID) is None
    assert hass.states.get("climate.renamed_gree_ac").state == HVACMode.COOL

    for entity_id in (
        "number.gree_ac_timer",
        "select.gree_ac_fresh_air",
        "switch.gree_ac_turbo",
    ):
        assert hass.states.get(entity_id).state != STATE_UNAVAILABLE
    mock_infrared_emitter_entity.send_command_calls.clear()
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: "number.gree_ac_timer", "value": 0.5},
        blocking=True,
    )
    await _flush_coalesced(hass)
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: "select.gree_ac_fresh_air", "option": "level_1"},
        blocking=True,
    )
    await _flush_coalesced(hass)
    await hass.services.async_call(
        "switch",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.gree_ac_turbo"},
        blocking=True,
    )
    await _flush_coalesced(hass)
    assert hass.states.get("number.gree_ac_timer").state == "0.5"
    assert hass.states.get("select.gree_ac_fresh_air").state == "level_1"
    assert hass.states.get("switch.gree_ac_turbo").state == "on"
    assert len(mock_infrared_emitter_entity.send_command_calls) == 3
    command = mock_infrared_emitter_entity.send_command_calls[-1]
    assert command.timer_hours == 0.5
    assert command.fresh_air == 1
    assert command.turbo


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_cancelled_timer_replacement_preserves_expiry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The old timer expires after cancellation without another successful send."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    deadline = climate._timer_deadline
    assert deadline is not None
    sends = len(mock_infrared_emitter_entity.send_command_calls)
    started = asyncio.Event()

    async def blocked_send(command: GreeAcCommand) -> None:
        started.set()
        await asyncio.Event().wait()

    with patch.object(mock_infrared_emitter_entity, "async_send_command", blocked_send):
        await climate.async_set_timer_hours(0.5)
        flush_task = hass.async_create_task(_flush_now(hass, climate))
        await started.wait()
        task = hass.async_create_task(climate.async_set_timer_hours(1.0))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        flush_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await flush_task

    freezer.move_to(deadline)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("number.gree_ac_timer").state == "0.0"
    assert climate._timer_deadline is None
    assert len(mock_infrared_emitter_entity.send_command_calls) == sends


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.SWITCH]])
@pytest.mark.parametrize("extra_entry_data", [{CONF_MODEL: MODEL_YAP1F}], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_pending_option_stays_private_during_state_publication(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """A staged option publishes optimistically; availability cannot hide it."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_coalesced(hass)
    assert hass.states.get("switch.gree_ac_turbo").state == "off"

    await climate.async_set_option("turbo", True)
    climate._state.async_notify_switches()
    await hass.async_block_till_done()
    assert hass.states.get("switch.gree_ac_turbo").state == "on"
    assert climate.extra_restore_state_data.as_dict()["turbo"] is True

    await _flush_coalesced(hass)
    assert mock_infrared_emitter_entity.send_command_calls[-1].turbo is True
    assert hass.states.get("switch.gree_ac_turbo").state == "on"


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.parametrize("extra_entry_data", [{CONF_MODEL: MODEL_YAP1F}], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_detached_climate_ignores_queued_received_signal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A received callback queued for the old owner cannot mutate shared options."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    before = climate.extra_restore_state_data.as_dict()
    await climate._state.command_lock.acquire()
    task = hass.async_create_task(
        climate._async_handle_signal(
            InfraredReceivedSignal(
                timings=GreeAcCommand(
                    model=GreeAcModel.YAP1F,
                    mode=GreeAcMode.COOL,
                    temperature=24,
                    turbo=True,
                ).get_raw_timings()
            )
        )
    )
    await asyncio.sleep(0)
    climate._state.climate = None
    climate._state.command_lock.release()
    await task
    assert climate.extra_restore_state_data.as_dict() == before


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_fan_edit_after_timer_deadline_reconciles_without_send(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Past the deadline, a fan edit flips assumed power before building a frame."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    deadline = climate._timer_deadline
    assert deadline is not None
    sends_before = len(mock_infrared_emitter_entity.send_command_calls)
    freezer.move_to(deadline)

    with patch.object(
        mock_infrared_emitter_entity,
        "async_send_command",
        side_effect=HomeAssistantError("must not send"),
    ):
        await climate.async_set_fan_mode(FAN_LOW)
        await _flush_now(hass, climate)

    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(_CLIMATE_ENTITY_ID).state == HVACMode.OFF
    assert hass.states.get("number.gree_ac_timer").state == "0.0"
    assert climate._timer_deadline is None
    assert climate._attr_fan_mode == FAN_LOW
    assert len(mock_infrared_emitter_entity.send_command_calls) == sends_before


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_pending_fan_edit_does_not_prevent_timer_power_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A fan edit staged before expiry cannot keep the AC powered on."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    deadline = climate._timer_deadline
    assert deadline is not None

    await climate.async_set_fan_mode(FAN_LOW)
    freezer.move_to(deadline)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_CLIMATE_ENTITY_ID).state == HVACMode.OFF
    assert hass.states.get("number.gree_ac_timer").state == "0.0"
    await _flush_now(hass, climate)
    command = mock_infrared_emitter_entity.send_command_calls[-1]
    assert command.power is False
    assert command.fan is GreeAcFanSpeed.LOW


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.parametrize(
    ("initial_mode", "expected_mode", "additional_sends"),
    [(HVACMode.COOL, HVACMode.OFF, 0), (HVACMode.OFF, HVACMode.COOL, 1)],
)
@pytest.mark.usefixtures("init_integration")
async def test_timer_expiry_updates_power_before_next_command(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
    initial_mode: HVACMode,
    expected_mode: HVACMode,
    additional_sends: int,
) -> None:
    """The device timer changes assumed power without sending another frame."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_hvac_mode(initial_mode)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    sends = len(mock_infrared_emitter_entity.send_command_calls)

    freezer.move_to(freezer() + timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(_CLIMATE_ENTITY_ID).state == expected_mode
    assert hass.states.get("number.gree_ac_timer").state == "0.0"
    assert len(mock_infrared_emitter_entity.send_command_calls) == sends

    await climate.async_set_fan_mode(FAN_LOW)
    await _flush_now(hass, climate)
    assert (
        len(mock_infrared_emitter_entity.send_command_calls) == sends + additional_sends
    )
    assert mock_infrared_emitter_entity.send_command_calls[-1].power
    await climate.async_turn_off()
    await _flush_now(hass, climate)
    command = mock_infrared_emitter_entity.send_command_calls[-1]
    assert not command.power
    assert command.mode is GreeAcMode.COOL
    assert command.timer_hours is None


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE, Platform.NUMBER]])
@pytest.mark.usefixtures("init_integration")
async def test_overdue_timer_reconciled_before_queued_fan_edit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A fan edit waiting ahead of expiry cleanup must not restart the unit."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    await climate.async_set_hvac_mode(HVACMode.COOL)
    await _flush_now(hass, climate)
    await climate.async_set_timer_hours(0.5)
    await _flush_now(hass, climate)
    deadline = climate._timer_deadline
    assert deadline is not None
    sends_before = len(mock_infrared_emitter_entity.send_command_calls)

    await climate._state.command_lock.acquire()
    try:
        fan_task = hass.async_create_task(climate.async_set_fan_mode(FAN_LOW))
        await asyncio.sleep(0)
        freezer.move_to(deadline)
        async_fire_time_changed(hass)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    finally:
        climate._state.command_lock.release()

    await fan_task
    await hass.async_block_till_done()

    assert hass.states.get(_CLIMATE_ENTITY_ID).state == HVACMode.OFF
    assert hass.states.get("number.gree_ac_timer").state == "0.0"
    assert climate._timer_deadline is None
    assert climate._attr_fan_mode == FAN_LOW
    # Fan edit while assumed off updates local fan only; no power-on frame.
    assert len(mock_infrared_emitter_entity.send_command_calls) == sends_before
