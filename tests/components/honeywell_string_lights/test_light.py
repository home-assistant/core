"""Tests for the Honeywell String Lights light platform."""

from __future__ import annotations

from homeassistant.components.honeywell_string_lights.light import COMMANDS
from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.radio_frequency.conftest import MockRadioFrequencyEntity

ENTITY_ID = "light.honeywell_string_lights"


async def test_turn_on_off_sends_commands(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    init_string_lights: MockConfigEntry,
) -> None:
    """Test turning the light on and off sends the correct RF commands."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_ASSUMED_STATE] is True

    context = Context()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        context=context,
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.context is context
    assert len(mock_rf_entity.send_command_calls) == 1
    command = mock_rf_entity.send_command_calls[0]
    assert command.command is COMMANDS.load_command("turn_on")
    assert command.context is context

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        context=context,
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.context is context
    assert len(mock_rf_entity.send_command_calls) == 2
    command = mock_rf_entity.send_command_calls[1]
    assert command.command is COMMANDS.load_command("turn_off")
    assert command.context is context


async def test_restore_state(
    hass: HomeAssistant,
    mock_rf_entity: MockRadioFrequencyEntity,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light restores its previous on state."""
    mock_restore_cache(hass, [State(ENTITY_ID, STATE_ON)])
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_unload_entry(
    hass: HomeAssistant, init_string_lights: MockConfigEntry
) -> None:
    """Test unloading the config entry removes the entity."""
    assert hass.states.get(ENTITY_ID) is not None

    assert await hass.config_entries.async_unload(init_string_lights.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
