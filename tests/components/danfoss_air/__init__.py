"""Tests for the Danfoss Air integration."""

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Danfoss Air config entry and update the switches."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Switches are added without update_before_add, so they have no state
    # until their first update.
    for entity_id in hass.states.async_entity_ids(SWITCH_DOMAIN):
        await async_update_entity(hass, entity_id)
