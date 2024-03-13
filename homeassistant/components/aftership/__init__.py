"""The AfterShip integration."""
from __future__ import annotations

from pyaftership import AfterShip, AfterShipException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AfterShip from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass)
    aftership = AfterShip(api_key=entry.data[CONF_API_KEY], session=session)

    try:
        await aftership.trackings.list()
    except AfterShipException as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = aftership

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
