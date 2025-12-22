"""The OpenEVSE integration."""

from __future__ import annotations

import openevsewifi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

type OpenEVSEConfigEntry = ConfigEntry[openevsewifi.Charger]


async def async_setup_entry(hass: HomeAssistant, entry: OpenEVSEConfigEntry) -> bool:
    """Set up openevse from a config entry."""

    entry.runtime_data = openevsewifi.Charger(entry.data[CONF_HOST])
    try:
        await hass.async_add_executor_job(entry.runtime_data.getStatus)
    except AttributeError as ex:
        raise ConfigEntryError("Unable to connect to charger") from ex

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
