"""Tests for the Gree Infrared climate platform."""

import asyncio
from typing import Any
from unittest.mock import patch

from infrared_protocols.commands.gree_ac import (
    MIN_TEMP,
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcMode,
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
from homeassistant.components.infrared import InfraredCommand, InfraredReceivedSignal
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.common import (
    MockConfigEntry,
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


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_receiver_off_signal_in_unconfigured_mode_keeps_the_last_active_mode(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test an off frame in an unconfigured mode is recorded with the last mode.

    The unit is off either way, so the frame still applies, but its mode is not one
    this entry may send and the next power-off frame carries the one before it.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.DRY},
        blocking=True,
    )
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                power=False,
                mode=GreeAcMode.HEAT,
                temperature=24,
                fan=GreeAcFanSpeed.HIGH,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.OFF
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
            temperature=24,
            fan=GreeAcFanSpeed.HIGH,
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
async def test_next_frame_keeps_what_the_remote_set(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test the fields this entity does not expose survive the next frame sent.

    Every frame carries the whole state, so the louvres and feature flags the
    physical remote set would otherwise be reset by the next frame HA sends.
    """
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.COOL,
                temperature=24,
                fan=GreeAcFanSpeed.AUTO,
                swing_v=True,
                swing_h=True,
                turbo=True,
                display=False,
                blow=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()

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
            mode=GreeAcMode.COOL,
            temperature=26,
            fan=GreeAcFanSpeed.AUTO,
            swing_v=True,
            swing_h=True,
            turbo=True,
            display=False,
            blow=True,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_remote_frame_during_send_is_kept(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a remote frame landing mid-send is not undone once the send finishes.

    The send only asked for a temperature, so every other field keeps what the
    remote set while it was going out, mode included.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    sending = asyncio.Event()
    finish_sending = asyncio.Event()
    send_command = mock_infrared_emitter_entity.async_send_command

    async def blocking_send(command: InfraredCommand) -> None:
        """Hold the frame in flight until the remote frame has been received."""
        sending.set()
        await finish_sending.wait()
        await send_command(command)

    with patch.object(
        mock_infrared_emitter_entity, "async_send_command", blocking_send
    ):
        temperature_call = hass.async_create_task(
            hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, ATTR_TEMPERATURE: 25},
                blocking=True,
            )
        )
        await sending.wait()
        mock_infrared_receiver_entity._handle_received_signal(
            InfraredReceivedSignal(
                timings=GreeAcCommand(
                    mode=GreeAcMode.DRY,
                    temperature=27,
                    fan=GreeAcFanSpeed.HIGH,
                    swing_v=True,
                ).get_raw_timings()
            )
        )
        finish_sending.set()
        await temperature_call

    state = hass.states.get(_CLIMATE_ENTITY_ID)
    assert state is not None
    assert state.state == HVACMode.DRY
    assert state.attributes["fan_mode"] == FAN_HIGH
    assert state.attributes[ATTR_TEMPERATURE] == 25
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
            temperature=25,
            fan=GreeAcFanSpeed.HIGH,
            swing_v=True,
        ).get_raw_timings()
    )


@pytest.mark.parametrize("has_receiver", [True])
@pytest.mark.usefixtures("init_integration")
async def test_unconfigured_mode_frame_is_not_carried(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    mock_infrared_receiver_entity: MockInfraredReceiverEntity,
) -> None:
    """Test a frame in an unconfigured mode is dropped whole, flags included.

    A mode the user did not configure is another unit's, so its flags must not reach
    the frames sent to this one.
    """
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: _CLIMATE_ENTITY_ID, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    mock_infrared_receiver_entity._handle_received_signal(
        InfraredReceivedSignal(
            timings=GreeAcCommand(
                mode=GreeAcMode.HEAT,
                temperature=24,
                fan=GreeAcFanSpeed.HIGH,
                swing_v=True,
                turbo=True,
            ).get_raw_timings()
        )
    )
    await hass.async_block_till_done()
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
