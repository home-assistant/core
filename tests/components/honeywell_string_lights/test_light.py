"""Tests for the Honeywell String Lights light platform."""

from __future__ import annotations

from rf_protocols import HoneywellStringLightsTurnOff, HoneywellStringLightsTurnOn

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
)
from homeassistant.core import HomeAssistant, State

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.radio_frequency.conftest import MockRadioFrequencyEntity

ENTITY_ID = "light.honeywell_string_lights"


async def test_turn_on_off_sends_commands(
    hass: HomeAssistant,
    mock_transmitter: MockRadioFrequencyEntity,
    init_integration: MockConfigEntry,
) -> None:
    """Test turning the light on and off sends the correct RF commands."""
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ASSUMED_STATE] is True

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == STATE_ON
    assert len(mock_transmitter.send_command_calls) == 1
    command = mock_transmitter.send_command_calls[0]
    assert isinstance(command, HoneywellStringLightsTurnOn)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    assert len(mock_transmitter.send_command_calls) == 2
    assert isinstance(
        mock_transmitter.send_command_calls[1], HoneywellStringLightsTurnOff
    )


async def test_restore_state(
    hass: HomeAssistant,
    mock_transmitter: MockRadioFrequencyEntity,
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
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test unloading the config entry removes the entity."""
    assert hass.states.get(ENTITY_ID) is not None

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
