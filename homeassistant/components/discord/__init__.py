"""The discord integration."""
from aiohttp.client_exceptions import ClientConnectorError
import nextcord

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import discovery

from .const import DOMAIN

PLATFORMS = [Platform.NOTIFY, Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discord from a config entry."""
    nextcord.VoiceClient.warn_nacl = False
    hass.data.setdefault(DOMAIN, {}).setdefault(
        entry.entry_id,
        dict(entry.data),
    )["client"] = discord_bot = nextcord.Client()
    try:
        await discord_bot.login(entry.data[CONF_API_TOKEN])
    except nextcord.LoginFailure as ex:
        raise ConfigEntryAuthFailed("Invalid token given") from ex
    except (ClientConnectorError, nextcord.HTTPException, nextcord.NotFound) as ex:
        raise ConfigEntryNotReady("Failed to connect") from ex

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            hass.data[DOMAIN][entry.entry_id],
            hass.data[DOMAIN],
        )
    )
    hass.config_entries.async_setup_platforms(entry, [Platform.CALENDAR])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Close the discord client connection and pop the shared data."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id]["client"].close()
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
