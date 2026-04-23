"""The kraken integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DISPATCH_CONFIG_UPDATED
from .coordinator import KrakenConfigEntry, KrakenData

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


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
    async_dispatcher_send(hass, DISPATCH_CONFIG_UPDATED, hass, config_entry)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.version == 1 and entry.minor_version == 1:
        _LOGGER.debug(
            "Migrating from version %s.%s", entry.version, entry.minor_version
        )
        options = dict(entry.options)
        options.pop(CONF_SCAN_INTERVAL, None)
        hass.config_entries.async_update_entry(entry, options=options, minor_version=2)
        _LOGGER.debug(
            "Migration to version %s.%s successful", entry.version, entry.minor_version
        )

    return True
