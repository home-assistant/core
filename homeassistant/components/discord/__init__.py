"""The discord integration."""
from aiohttp.client_exceptions import ClientConnectorError
import discord

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PLATFORM, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

PLATFORMS = [Platform.NOTIFY]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Discord component."""
    # Iterate all entries for notify to only get Discord
    if Platform.NOTIFY in config:
        for entry in config[Platform.NOTIFY]:
            if entry[CONF_PLATFORM] == DOMAIN:
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                    )
                )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discord from a config entry."""
    discord.VoiceClient.warn_nacl = False
    discord_bot = discord.Client()
    try:
        await discord_bot.login(entry.data[CONF_TOKEN])
    except discord.LoginFailure as ex:
        raise ConfigEntryAuthFailed("Invalid token given") from ex
    except (ClientConnectorError, discord.HTTPException, discord.NotFound) as ex:
        raise ConfigEntryNotReady("Failed to connect") from ex
    await discord_bot.close()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            hass.data[DOMAIN][entry.entry_id],
            hass.data[DOMAIN],
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
