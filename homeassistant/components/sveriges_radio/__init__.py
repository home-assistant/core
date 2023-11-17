"""The Sveriges Radio integration."""
from __future__ import annotations

from sverigesradio import SverigesRadio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sveriges Radio from a config entry.

    This integration doesn't set up any entities, as it provides a media source
    only.
    """
    session = async_get_clientsession(hass)
    sr_radio = SverigesRadio(session=session, user_agent=f"HomeAssistant/{__version__}")

    hass.data[DOMAIN] = sr_radio
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    del hass.data[DOMAIN]
    return True
