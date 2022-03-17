"""The discord integration."""
from aiohttp.client_exceptions import ClientConnectorError
import nextcord

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_PLATFORM, Platform
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
    nextcord.VoiceClient.warn_nacl = False
    discord_bot = nextcord.Client()
    try:
        await discord_bot.login(entry.data[CONF_API_TOKEN])
    except nextcord.LoginFailure as ex:
        await discord_bot.close()
        raise ConfigEntryAuthFailed("Invalid token given") from ex
    except (ClientConnectorError, nextcord.HTTPException, nextcord.NotFound) as ex:
        await discord_bot.close()
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
