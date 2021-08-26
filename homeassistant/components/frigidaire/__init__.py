"""The frigidaire integration."""
from __future__ import annotations

import frigidaire

from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up frigidaire from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    def setup(username: str, password: str) -> frigidaire.Frigidaire:
        try:
            hass.data[DOMAIN][entry.entry_id] = frigidaire.Frigidaire(
                username, password, timeout=60
            )
        except ConnectionError as err:
            raise ConfigEntryNotReady("Cannot connect to Frigidaire") from err
        except frigidaire.FrigidaireException as err:
            raise data_entry_flow.AbortFlow from err

    await hass.async_add_executor_job(
        setup, entry.data["username"], entry.data["password"]
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
