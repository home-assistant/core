"""The homecom integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import _LOGGER, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .hub import Hub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up homecom from a config entry."""
    username: str | None = entry.data.get("username")
    password: str | None = entry.data.get("password")
    if username is not None and password is not None:
        hub = Hub(
            hass,
            async_get_clientsession(hass),
            username,
            password,
        )
        await hub.authenticate()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        return True

    _LOGGER.warning(
        "Username or password is not set. Please set it in the integration settings"
    )
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
