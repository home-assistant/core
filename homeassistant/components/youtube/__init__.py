"""Support for YouTube."""

from types import MappingProxyType

from aiohttp.client_exceptions import ClientError

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AsyncConfigEntryAuth
from .const import (
    ATTR_TITLE,
    CONF_CHANNEL_ID,
    CONF_CHANNELS,
    DOMAIN,
    SUBENTRY_TYPE_CHANNEL,
)
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

    entry.runtime_data = {}
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_CHANNEL):
        coordinator = YouTubeDataUpdateCoordinator(hass, entry, subentry, auth)
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data[subentry.subentry_id] = coordinator
        if (title := coordinator.data[ATTR_TITLE]) != subentry.title:
            hass.config_entries.async_update_subentry(entry, subentry, title=title)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: YouTubeConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_update_listener(hass: HomeAssistant, entry: YouTubeConfigEntry) -> None:
    """Reload the config entry when it or one of its subentries is updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entries to the subentry structure."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_"
    for channel_id in dict.fromkeys(entry.options.get(CONF_CHANNELS, [])):
        subentry = ConfigSubentry(
            data=MappingProxyType({CONF_CHANNEL_ID: channel_id}),
            subentry_type=SUBENTRY_TYPE_CHANNEL,
            title=channel_id,
            unique_id=channel_id,
        )
        hass.config_entries.async_add_subentry(entry, subentry)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{prefix}{channel_id}"), entry.entry_id
        )
        if device is not None:
            device_registry.async_update_device(
                device.id,
                new_identifiers={(DOMAIN, channel_id)},
                new_config_subentry_id=subentry.subentry_id,
            )
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if not entity_entry.unique_id.startswith(f"{prefix}{channel_id}_"):
                continue
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                new_unique_id=entity_entry.unique_id.removeprefix(prefix),
                config_subentry_id=subentry.subentry_id,
            )
    hass.config_entries.async_update_entry(entry, version=2, options={})
    return True
