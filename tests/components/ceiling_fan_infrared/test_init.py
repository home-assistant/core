"""Tests for the Ceiling Fan Infrared integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity

from homeassistant.components.ceiling_fan_infrared.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_INFRARED_ENTITY_UUID,
)
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

RENAMED_EMITTER_ENTITY_ID = "infrared.renamed_emitter"


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
async def test_setup_stores_the_emitter_registry_uuid(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the emitter registry UUID is stored for entries without one."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry_entry = entity_registry.async_get(EMITTER_ENTITY_ID)
    assert registry_entry is not None
    assert config_entry.data[CONF_INFRARED_ENTITY_UUID] == registry_entry.id


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_state_survives_a_reload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the assumed state is restored when the entry is reloaded."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    fan_entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert fan_entity_id is not None
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: 66},
        blocking=True,
    )

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(fan_entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 66


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_entry_follows_the_emitter_when_it_is_renamed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
) -> None:
    """Test the entry keeps working and keeps its state when the emitter is renamed."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    fan_entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert fan_entity_id is not None
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: fan_entity_id, ATTR_PERCENTAGE: 66},
        blocking=True,
    )
    mock_infrared_emitter_entity.send_command_calls.clear()

    entity_registry.async_update_entity(
        EMITTER_ENTITY_ID, new_entity_id=RENAMED_EMITTER_ENTITY_ID
    )
    await hass.async_block_till_done()

    renamed_entry = entity_registry.async_get(RENAMED_EMITTER_ENTITY_ID)
    assert renamed_entry is not None
    assert config_entry.data == {
        CONF_INFRARED_ENTITY_ID: RENAMED_EMITTER_ENTITY_ID,
        CONF_INFRARED_ENTITY_UUID: renamed_entry.id,
    }
    assert config_entry.state is ConfigEntryState.LOADED

    assert (state := hass.states.get(fan_entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] == 66

    # A reload must not reset the assumed state: turning on an already on fan
    # would send a second toggle and physically turn it off.
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )

    assert mock_infrared_emitter_entity.send_command_calls == []


@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_emitter_renamed_while_unloaded_is_followed_on_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a rename made while the entry is unloaded is picked up on setup."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_registry.async_update_entity(
        EMITTER_ENTITY_ID, new_entity_id=RENAMED_EMITTER_ENTITY_ID
    )
    await hass.async_block_till_done()

    assert config_entry.data[CONF_INFRARED_ENTITY_ID] == EMITTER_ENTITY_ID

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.data[CONF_INFRARED_ENTITY_ID] == RENAMED_EMITTER_ENTITY_ID

    fan_entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert fan_entity_id is not None
    assert (state := hass.states.get(fan_entity_id)) is not None
    assert state.state != STATE_UNAVAILABLE
