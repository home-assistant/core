"""Tests for the Ceiling Fan Infrared integration setup."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID

from homeassistant.components.ceiling_fan_infrared.const import CONF_INFRARED_ENTITY_ID
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
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
    assert config_entry.data == {CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID}

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = config_entry.state
    assert state is ConfigEntryState.NOT_LOADED


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
async def test_unknown_speed_survives_a_reload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an unknown speed is not restored as 0 %, which would mean off."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    fan_entity_id = entity_registry.async_get_entity_id(
        FAN_DOMAIN, "ceiling_fan_infrared", config_entry.entry_id
    )
    assert fan_entity_id is not None
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: fan_entity_id},
        blocking=True,
    )
    assert (state := hass.states.get(fan_entity_id)) is not None
    assert state.attributes[ATTR_PERCENTAGE] is None

    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(fan_entity_id)) is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_PERCENTAGE] is None
