"""The Gryf Smart integration."""

from __future__ import annotations

from pygryfsmart.api import GryfApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_API, CONF_COMMUNICATION, CONF_DEVICE_DATA, CONF_PORT, DOMAIN

_PLATFORMS: list[Platform] = [
    Platform.LIGHT,
    # Platform.BINARY_SENSOR,
    # Platform.SENSOR,
    # Platform.CLIMATE,
    # Platform.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Config flow for Gryf Smart Integration."""

    try:
        api = GryfApi(entry.data[CONF_COMMUNICATION][CONF_PORT])
        await api.start_connection()
        api.start_update_interval(1)
    except ConnectionError:
        raise ConfigEntryNotReady("Unable to connect with device") from ConnectionError

    entry.runtime_data = {}
    entry.runtime_data[CONF_API] = api
    entry.runtime_data[CONF_DEVICE_DATA] = {
        "identifiers": {(DOMAIN, "Gryf Smart", entry.unique_id)},
        "name": f"Gryf Smart {entry.unique_id}",
        "manufacturer": "Gryf Smart",
        "model": "serial",
        "sw_version": "1.0.0",
        "hw_version": "1.0.0",
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
