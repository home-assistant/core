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
    channel_ids = dict.fromkeys(entry.options.get(CONF_CHANNELS, []))

    subentries: dict[str, ConfigSubentry] = {}
    for channel_id in channel_ids:
        subentry = ConfigSubentry(
            data=MappingProxyType({CONF_CHANNEL_ID: channel_id}),
            subentry_type=SUBENTRY_TYPE_CHANNEL,
            title=channel_id,
            unique_id=channel_id,
        )
        hass.config_entries.async_add_subentry(entry, subentry)
        subentries[channel_id] = subentry

    # Attach the entities of tracked channels to their subentry and remove
    # entities left behind by channels which are no longer tracked.
    channel_prefixes = {
        f"{prefix}{channel_id}_": channel_id for channel_id in channel_ids
    }
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        channel_subentry = next(
            (
                subentries[channel_id]
                for channel_prefix, channel_id in channel_prefixes.items()
                if entity_entry.unique_id.startswith(channel_prefix)
            ),
            None,
        )
        if channel_subentry is None:
            entity_registry.async_remove(entity_entry.entity_id)
        else:
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                config_subentry_id=channel_subentry.subentry_id,
            )

    # Move the devices of tracked channels to their subentry and remove
    # devices left behind by channels which are no longer tracked.
    for device_entry in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        channel_id = next(
            (
                identifier[1].removeprefix(prefix)
                for identifier in device_entry.identifiers
                if identifier[0] == DOMAIN and identifier[1].startswith(prefix)
            ),
            None,
        )
        if channel_id is not None and channel_id in subentries:
            device_registry.async_update_device(
                device_entry.id,
                new_identifiers={(DOMAIN, channel_id)},
                new_config_subentry_id=subentries[channel_id].subentry_id,
            )
        else:
            device_registry.async_remove_device(device_entry.id)

    hass.config_entries.async_update_entry(entry, version=2, options={})
    return True
