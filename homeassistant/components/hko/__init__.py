"""The Hong Kong Observatory integration."""

from __future__ import annotations

from hko import LOCATIONS

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LOCATION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_DISTRICT, DOMAIN, KEY_DISTRICT, KEY_LOCATION
from .coordinator import HKOUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hong Kong Observatory from a config entry."""

    location = entry.data[CONF_LOCATION]
    district = next(
        (item for item in LOCATIONS if item[KEY_LOCATION] == location),
        {KEY_DISTRICT: DEFAULT_DISTRICT},
    )[KEY_DISTRICT]
    websession = async_get_clientsession(hass)

    coordinator = HKOUpdateCoordinator(hass, websession, district, location)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
