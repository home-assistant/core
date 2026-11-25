"""Tests for the Danfoss Air integration."""

from homeassistant.components.danfoss_air import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.setup import async_setup_component

CONFIG = {DOMAIN: {CONF_HOST: "192.0.2.1"}}


async def setup_integration(hass: HomeAssistant) -> None:
    """Set up the Danfoss Air integration from YAML and update the switches."""
    assert await async_setup_component(hass, DOMAIN, CONFIG)
    await hass.async_block_till_done(wait_background_tasks=True)

    # Switches are added without update_before_add, so they have no state
    # until their first update.
    for entity_id in hass.states.async_entity_ids(SWITCH_DOMAIN):
        await async_update_entity(hass, entity_id)
