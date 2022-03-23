"""Tests for the samsungtv component."""


from homeassistant.components.samsungtv.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_samsungtv_entry(hass: HomeAssistant, data: ConfigType) -> ConfigEntry:
    """Set up mock Samsung TV from config entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, entry_id="123456", unique_id="any"
    )
    entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    return entry
