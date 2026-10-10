"""The discord integration."""

from aiohttp.client_exceptions import ClientConnectorError
import nextcord

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    discovery,
)
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ENTRY, DATA_HASS_CONFIG, DOMAIN

type DiscordConfigEntry = ConfigEntry[None]

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Discord component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DiscordConfigEntry) -> bool:
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

    # Legacy notify service, kept for backwards compatibility with automations
    # relying on embeds and attachments passed through the service data. The entry
    # is passed so the service can unregister itself on unload.
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {**entry.data, CONF_ENTRY: entry},
            hass.data[DATA_HASS_CONFIG],
        )
    )

    # Create the shared bot device before the platforms are set up, so per-target
    # devices can resolve it as their via_device.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id, **bot_device_info(entry)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: DiscordConfigEntry
) -> None:
    """Reload the entry when its data or subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: DiscordConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def bot_device_info(entry: DiscordConfigEntry) -> dr.DeviceInfo:
    """Return device info for the shared bot device."""
    return dr.DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        entry_type=dr.DeviceEntryType.SERVICE,
        manufacturer="Discord",
        name=entry.title,
    )
