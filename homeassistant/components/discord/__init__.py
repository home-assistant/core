"""The discord integration."""

from aiohttp.client_exceptions import ClientConnectorError
import nextcord

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Discord component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Discord from a config entry."""
    nextcord.VoiceClient.warn_nacl = False
    discord_bot = nextcord.Client()
    try:
        await discord_bot.login(entry.data[CONF_API_TOKEN])
    except nextcord.LoginFailure as ex:
        raise ConfigEntryAuthFailed("Invalid token given") from ex
    except (ClientConnectorError, nextcord.HTTPException, nextcord.NotFound) as ex:
        raise ConfigEntryNotReady("Failed to connect") from ex
    finally:
        await discord_bot.close()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.NOTIFY, DOMAIN, dict(entry.data), hass.data[DATA_HASS_CONFIG]
        )
    )

    return True
