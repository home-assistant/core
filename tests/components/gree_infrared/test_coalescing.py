"""Coalescing tests: rapid changes share one IR frame (one beep)."""

import asyncio
import contextlib
from unittest.mock import patch

from infrared_protocols.commands.gree_ac import (
    GreeAcCommand,
    GreeAcFanSpeed,
    GreeAcMode,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.climate import HVACMode
from homeassistant.components.gree_infrared.const import (
    CONF_HVAC_MODES,
    DOMAIN,
    MODEL_YAP1F,
)
from homeassistant.components.gree_infrared.state import COALESCE_DELAY_SEC
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, CONF_MODEL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ENTRY_ID

_CLIMATE = "climate.gree_ac"


@pytest.fixture
def platforms() -> list[Platform]:
    """Load only the climate and switch platforms for these tests."""
    return [Platform.CLIMATE, Platform.SWITCH]


@pytest.fixture
def has_receiver() -> bool:
    """No receiver needed for transmit coalescing."""
    return False


@pytest.fixture
def extra_entry_data(hvac_modes: list[HVACMode]) -> dict:
    """Use the YAP1F profile so the turbo switch exists."""
    return {CONF_HVAC_MODES: hvac_modes, CONF_MODEL: MODEL_YAP1F}


def _turbo_entity_id(hass: HomeAssistant) -> str:
    """Resolve the turbo switch independently of its display name."""
    entity_id = er.async_get(hass).async_get_entity_id(
        "switch", DOMAIN, f"{ENTRY_ID}_turbo"
    )
    assert entity_id is not None
    return entity_id


async def _flush(hass: HomeAssistant) -> None:
    """Wait out the coalescing window, then drain the flush task."""
    await asyncio.sleep(COALESCE_DELAY_SEC + 0.2)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
async def test_single_call_sends_one_frame(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """A single isolated change still transmits exactly one frame."""
    assert mock_infrared_emitter_entity.send_command_calls == []
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await _flush(hass)
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert command.power is True
    assert command.mode is GreeAcMode.COOL


@pytest.mark.usefixtures("init_integration")
async def test_three_quick_calls_coalesce_into_one_frame(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Mode + temp + fan + turbo inside one window share a single frame."""
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await _flush(hass)
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    mock_infrared_emitter_entity.send_command_calls.clear()

    # Mirrors automation 1711273280810: temperature, fan and turbo in sequence.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {ATTR_ENTITY_ID: _CLIMATE, ATTR_TEMPERATURE: 24},
        blocking=True,
    )
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "fan_mode": "high"},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_on",
        {ATTR_ENTITY_ID: _turbo_entity_id(hass)},
        blocking=True,
    )
    await _flush(hass)

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
    command = mock_infrared_emitter_entity.send_command_calls[0]
    assert command.power is True
    assert command.mode is GreeAcMode.COOL
    assert command.temperature == 24
    assert command.fan is GreeAcFanSpeed.HIGH
    assert command.turbo is True


@pytest.mark.usefixtures("init_integration")
async def test_calls_separated_by_window_send_twice(
    hass: HomeAssistant, mock_infrared_emitter_entity: MockInfraredEmitterEntity
) -> None:
    """Changes in separate quiet windows transmit separate frames."""
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )
    await _flush(hass)
    assert len(mock_infrared_emitter_entity.send_command_calls) == 1

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {ATTR_ENTITY_ID: _CLIMATE, "fan_mode": "low"},
        blocking=True,
    )
    await _flush(hass)
    assert len(mock_infrared_emitter_entity.send_command_calls) == 2
    assert mock_infrared_emitter_entity.send_command_calls[1].fan is (
        GreeAcFanSpeed.LOW
    )


@pytest.mark.usefixtures("init_integration")
async def test_unload_with_in_flight_flush_keeps_cancellation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Cancelling the unload task propagates while an in-flight flush runs."""
    climate = mock_config_entry.runtime_data.climate
    assert climate is not None
    state = climate._state
    started = asyncio.Event()

    async def blocked_send(command: GreeAcCommand) -> None:
        started.set()
        await asyncio.Event().wait()

    with patch.object(mock_infrared_emitter_entity, "async_send_command", blocked_send):
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {ATTR_ENTITY_ID: _CLIMATE, "hvac_mode": HVACMode.COOL},
            blocking=True,
        )
        await asyncio.sleep(COALESCE_DELAY_SEC + 0.2)
        await started.wait()
        in_flight = state._coalesce_task
        assert in_flight is not None and not in_flight.done()
        unload_task = hass.async_create_task(
            state.async_unload_coalesced_flush(climate._async_flush_coalesced)
        )
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        unload_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await unload_task

    in_flight.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await in_flight
