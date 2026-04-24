"""Tests for the Novy Hood fan platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.novy_hood.commands import NovyHoodMinus, NovyHoodPlus
from homeassistant.const import ATTR_ASSUMED_STATE, ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.radio_frequency.conftest import MockRadioFrequencyEntity

ENTITY_ID = "fan.novy_hood"


async def _set_percentage(hass: HomeAssistant, percentage: int) -> None:
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_PERCENTAGE: percentage},
        blocking=True,
    )


async def test_turn_on_from_off_sends_plus_once(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """Turning on from off sends `plus` once and lands at level 1 (25%)."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ASSUMED_STATE] is True

    with patch("homeassistant.components.novy_hood.entity.asyncio.sleep", AsyncMock()):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert len(mock_rf_entity.send_command_calls) == 1
    assert isinstance(mock_rf_entity.send_command_calls[0].command, NovyHoodPlus)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 25


async def test_turn_off_sends_four_minus(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """Turning off sends `minus` four times."""
    with patch("homeassistant.components.novy_hood.entity.asyncio.sleep", AsyncMock()):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert len(mock_rf_entity.send_command_calls) == 4
    assert all(
        isinstance(call.command, NovyHoodMinus)
        for call in mock_rf_entity.send_command_calls
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_PERCENTAGE] == 0


async def test_set_percentage_up(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """From level 0, setting 50% sends `plus` twice."""
    with patch("homeassistant.components.novy_hood.entity.asyncio.sleep", AsyncMock()):
        await _set_percentage(hass, 50)

    assert len(mock_rf_entity.send_command_calls) == 2
    assert all(
        isinstance(call.command, NovyHoodPlus)
        for call in mock_rf_entity.send_command_calls
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == 50


async def test_set_percentage_down(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """From level 4 (100%), setting 25% sends `minus` three times."""
    with patch("homeassistant.components.novy_hood.entity.asyncio.sleep", AsyncMock()):
        await _set_percentage(hass, 100)
        mock_rf_entity.send_command_calls.clear()
        await _set_percentage(hass, 25)

    assert len(mock_rf_entity.send_command_calls) == 3
    assert all(
        isinstance(call.command, NovyHoodMinus)
        for call in mock_rf_entity.send_command_calls
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == 25


async def test_set_percentage_noop(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """Setting the same percentage twice sends no additional commands."""
    with patch("homeassistant.components.novy_hood.entity.asyncio.sleep", AsyncMock()):
        await _set_percentage(hass, 50)
        mock_rf_entity.send_command_calls.clear()
        await _set_percentage(hass, 50)

    assert mock_rf_entity.send_command_calls == []
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == 50


async def test_set_percentage_zero_routes_to_turn_off(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_novy_hood: MockConfigEntry,
) -> None:
    """Setting 0% from any level routes through turn_off: four `minus` presses."""
    with patch("homeassistant.components.novy_hood.entity.asyncio.sleep", AsyncMock()):
        await _set_percentage(hass, 75)
        mock_rf_entity.send_command_calls.clear()
        await _set_percentage(hass, 0)

    assert len(mock_rf_entity.send_command_calls) == 4
    assert all(
        isinstance(call.command, NovyHoodMinus)
        for call in mock_rf_entity.send_command_calls
    )
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF


async def test_restore_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Restoring a 75% percentage brings the fan back to level 3."""
    mock_restore_cache(
        hass,
        [
            State(
                ENTITY_ID,
                STATE_ON,
                {ATTR_PERCENTAGE: 75},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == 75
