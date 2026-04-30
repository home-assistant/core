"""The kraken integration."""

from __future__ import annotations

from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DISPATCH_CONFIG_UPDATED
from .coordinator import KrakenConfigEntry, KrakenData

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: KrakenConfigEntry) -> bool:
    """Set up kraken from a config entry."""
    kraken_data = KrakenData(hass, entry)
    await kraken_data.async_setup()
    entry.runtime_data = kraken_data
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: KrakenConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_options_updated(
    hass: HomeAssistant, config_entry: KrakenConfigEntry
) -> None:
    """Triggered by config entry options updates."""
    config_entry.runtime_data.set_update_interval(
        config_entry.options[CONF_SCAN_INTERVAL]
    )
    async_dispatcher_send(hass, DISPATCH_CONFIG_UPDATED, hass, config_entry)
