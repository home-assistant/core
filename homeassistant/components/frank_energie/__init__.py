"""The Frank Energie component."""
from __future__ import annotations

from python_frank_energie import FrankEnergie

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_AUTH_TOKEN, CONF_REFRESH_TOKEN, DOMAIN
from .coordinator import FrankEnergieCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Frank Energie component from a config entry."""

    api = FrankEnergie(
        clientsession=async_get_clientsession(hass),
        auth_token=entry.data.get(CONF_AUTH_TOKEN, None),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN, None),
    )
    frank_coordinator = FrankEnergieCoordinator(hass, entry, api)

    await frank_coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = frank_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
