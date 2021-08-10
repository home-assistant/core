"""Tests for the samsungtv component."""
from homeassistant.components.samsungtv.const import DOMAIN as SAMSUNGTV_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_samsungtv(hass: HomeAssistant, config: dict):
    """Set up mock Samsung TV."""
    await async_setup_component(hass, "persistent_notification", {})
    entry = MockConfigEntry(domain=SAMSUNGTV_DOMAIN, data=config)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
