"""The duotecno integration."""
from __future__ import annotations

from duotecno.controller import PyDuotecno
from duotecno.exceptions import InvalidPassword, LoadFailure

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up duotecno from a config entry."""

    controller = PyDuotecno()
    try:
        await controller.connect(
            entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_PASSWORD]
        )
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except (OSError, InvalidPassword, LoadFailure) as err:
        raise ConfigEntryNotReady from err
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
