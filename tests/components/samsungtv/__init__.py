"""Tests for the samsungtv component."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.components.samsungtv.const import DOMAIN, ENTRY_RELOAD_COOLDOWN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def async_wait_config_entry_reload(hass: HomeAssistant) -> None:
    """Wait for the config entry to reload."""
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()


async def setup_samsungtv_entry(hass: HomeAssistant, data: ConfigType) -> ConfigEntry:
    """Set up mock Samsung TV from config entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=data, entry_id="123456", unique_id="any"
    )
    entry.add_to_hass(hass)

    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    return entry
