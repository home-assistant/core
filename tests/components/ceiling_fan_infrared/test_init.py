"""Tests for the Ceiling Fan Infrared integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.ceiling_fan_infrared.const import CONF_INFRARED_ENTITY_ID
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN, SERVICE_TURN_ON
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_setup_and_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading a config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state: ConfigEntryState = config_entry.state
    assert state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = config_entry.state
    assert state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_entry_follows_the_emitter_when_it_is_renamed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test the entry keeps working when the emitter entity ID changes."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry.async_update_entity(
        EMITTER_ENTITY_ID, new_entity_id="infrared.renamed_emitter"
    )
    await hass.async_block_till_done()

    assert config_entry.data[CONF_INFRARED_ENTITY_ID] == "infrared.renamed_emitter"
    assert config_entry.state is ConfigEntryState.LOADED

    fan_entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert fan_entity_id is not None
    assert (state := hass.states.get(fan_entity_id)) is not None
    assert state.state != STATE_UNAVAILABLE

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )

    assert len(mock_infrared_emitter_entity.send_command_calls) == 1
