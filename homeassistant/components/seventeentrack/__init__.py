"""The seventeentrack component."""

from py17track import Client as SeventeenTrackClient
from py17track.errors import SeventeenTrackError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up 17Track from a config entry."""

    session = async_get_clientsession(hass)
    client = SeventeenTrackClient(session=session)

    try:
        await client.profile.login(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    except SeventeenTrackError as err:
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
