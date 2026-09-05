"""Support for YouTube."""

from aiohttp.client_exceptions import ClientError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AsyncConfigEntryAuth
from .const import CONF_CHANNELS
from .coordinator import YouTubeConfigEntry, YouTubeDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: YouTubeConfigEntry) -> bool:
    """Set up YouTube from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(hass, session)
    try:
        await auth.check_and_refresh_token()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed(
            "OAuth session is not valid, reauth required"
        ) from err
    except (OAuth2TokenRequestError, ClientError) as err:
        raise ConfigEntryNotReady from err
    coordinator = YouTubeDataUpdateCoordinator(hass, entry, auth)

    await coordinator.async_config_entry_first_refresh()

    await delete_devices(hass, entry)

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: YouTubeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def delete_devices(hass: HomeAssistant, entry: YouTubeConfigEntry) -> None:
    """Delete devices for channels removed from the entry options."""
    channel_ids = set(entry.options[CONF_CHANNELS])
    device_registry = dr.async_get(hass)
    dev_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    for dev_entry in dev_entries:
        # Identifiers are (DOMAIN, f"{entry_id}_{channel_id}").
        if not any(
            identifier[1].removeprefix(f"{entry.entry_id}_") in channel_ids
            for identifier in dev_entry.identifiers
        ):
            device_registry.async_remove_device(dev_entry.id)
