"""The Philips Air Purifier integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .client import ReliableClient
from .const import COAP_PORT, DOMAIN

PLATFORMS: list[str] = [Platform.FAN]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Philips Air Purifier from a config entry."""

    client = ReliableClient(entry.data["host"], port=COAP_PORT)
    client.start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = hass.data[DOMAIN][entry.entry_id]
        client.stop()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
