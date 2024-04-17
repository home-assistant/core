"""The Radio Browser integration."""

from __future__ import annotations

from aiodns.error import DNSError
from radios import RadioBrowser, RadioBrowserError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Radio Browser from a config entry.

    This integration doesn't set up any entities, as it provides a media source
    only.
    """
    session = async_get_clientsession(hass)
    radios = RadioBrowser(session=session, user_agent=f"HomeAssistant/{__version__}")

    try:
        await radios.stats()
    except (DNSError, RadioBrowserError) as err:
        raise ConfigEntryNotReady("Could not connect to Radio Browser API") from err

    hass.data[DOMAIN] = radios
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    del hass.data[DOMAIN]
    return True
