"""Support for Enigma2 devices."""

from openwebif.api import OpenWebIfDevice
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Enigma2 from a config entry."""
    base_url = URL.build(
        scheme="http" if not entry.data[CONF_SSL] else "https",
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        user=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
    )

    session = async_create_clientsession(
        hass, verify_ssl=entry.data[CONF_VERIFY_SSL], base_url=base_url
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = OpenWebIfDevice(session)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
