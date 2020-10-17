"""Tests for Adaptive Lighting integration."""
from homeassistant import config_entries
from homeassistant.components import adaptive_lighting
from homeassistant.components.adaptive_lighting.const import (
    DEFAULT_NAME,
    UNDO_UPDATE_LISTENER,
)
from homeassistant.const import CONF_NAME
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_with_config(hass):
    """Test that we import the config and setup the integration."""
    config = {
        adaptive_lighting.DOMAIN: {
            adaptive_lighting.CONF_NAME: DEFAULT_NAME,
        }
    }
    assert await async_setup_component(hass, adaptive_lighting.DOMAIN, config)
    assert adaptive_lighting.DOMAIN in hass.data


async def test_successful_config_entry(hass):
    """Test that Adaptive Lighting is configured successfully."""

    entry = MockConfigEntry(
        domain=adaptive_lighting.DOMAIN,
        data={CONF_NAME: DEFAULT_NAME},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state == config_entries.ENTRY_STATE_LOADED

    assert UNDO_UPDATE_LISTENER in hass.data[adaptive_lighting.DOMAIN][entry.entry_id]


async def test_unload_entry(hass):
    """Test removing Adaptive Lighting."""
    entry = MockConfigEntry(
        domain=adaptive_lighting.DOMAIN,
        data={CONF_NAME: DEFAULT_NAME},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == config_entries.ENTRY_STATE_NOT_LOADED
    assert adaptive_lighting.DOMAIN not in hass.data
