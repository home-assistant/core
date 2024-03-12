"""The Arve integration."""

from __future__ import annotations

from asyncarve import Arve, ArveConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_SECRET,
    CONF_NAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .const import DATA_ARVE_CLIENT, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Arve from a config entry."""

    arve = Arve(
        entry.data[CONF_ACCESS_TOKEN],
        entry.data[CONF_CLIENT_SECRET],
        entry.data[CONF_NAME],
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {DATA_ARVE_CLIENT: arve}

    try:
        await arve.get_sensor_info()
    except ArveConnectionError as exception:
        raise ConfigEntryError from exception

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
