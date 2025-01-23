"""The Briiv Air Purifier integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import BriivAPI
from .const import CONF_SERIAL_NUMBER, DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Briiv from a config entry."""
    api = BriivAPI(
        host=entry.data["host"],
        port=entry.data["port"],
        serial_number=entry.data[CONF_SERIAL_NUMBER],
    )

    try:
        # Start the UDP listener
        await api.start_listening(hass.loop)
    except OSError as err:
        await api.stop_listening()
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    api: BriivAPI = hass.data[DOMAIN][entry.entry_id]
    await api.stop_listening()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
