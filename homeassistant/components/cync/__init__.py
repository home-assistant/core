"""The Cync integration."""

from pycync import Auth, Cync, CyncLight, User
from pycync.exceptions import AuthFailedError, CyncError

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import get_default_context

from .const import (
    CONF_AUTHORIZE_STRING,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DOMAIN,
)
from .coordinator import CyncConfigEntry, CyncCoordinator

_PLATFORMS: list[Platform] = [Platform.LIGHT]


def _migrate_unique_ids(
    hass: HomeAssistant, entry: CyncConfigEntry, cync: Cync
) -> None:
    """Migrate legacy light registry IDs to pycync's mesh-based unique IDs."""
    id_map = {
        f"{device.parent_home_id}-{device.device_id}": device.unique_id
        for home in cync.get_homes()
        for device in home.get_flattened_device_list()
        if isinstance(device, CyncLight)
        and f"{device.parent_home_id}-{device.device_id}" != device.unique_id
    }

    entity_registry = er.async_get(hass)
    migrated_device_ids = set()
    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if (
            entity_entry.platform == DOMAIN
            and entity_entry.domain == Platform.LIGHT
            and (new_unique_id := id_map.get(entity_entry.unique_id))
        ):
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                new_unique_id=new_unique_id,
            )
            if entity_entry.device_id is not None:
                migrated_device_ids.add(entity_entry.device_id)

    device_registry = dr.async_get(hass)
    for device_id in migrated_device_ids:
        device_entry = device_registry.async_get(device_id)
        if device_entry is None:
            continue
        new_identifiers = {
            (
                domain,
                id_map.get(identifier, identifier) if domain == DOMAIN else identifier,
            )
            for domain, identifier in device_entry.identifiers
        }
        if new_identifiers != device_entry.identifiers:
            device_registry.async_update_device(
                device_entry.id,
                new_identifiers=new_identifiers,
            )


async def _async_create_cync(hass: HomeAssistant, entry: CyncConfigEntry) -> Cync:
    """Create an authenticated Cync client."""
    user_info = User(
        entry.data[CONF_ACCESS_TOKEN],
        entry.data[CONF_REFRESH_TOKEN],
        entry.data[CONF_AUTHORIZE_STRING],
        entry.data[CONF_USER_ID],
        expires_at=entry.data[CONF_EXPIRES_AT],
    )
    cync_auth = Auth(async_get_clientsession(hass), user=user_info)
    ssl_context = get_default_context()

    try:
        return await Cync.create(
            auth=cync_auth,
            ssl_context=ssl_context,
        )
    except AuthFailedError as ex:
        raise ConfigEntryAuthFailed("User token invalid") from ex
    except CyncError as ex:
        raise ConfigEntryNotReady("Unable to connect to Cync") from ex


async def async_migrate_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Migrate an existing Cync config entry."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(entry, version=2)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Set up Cync from a config entry."""
    cync = await _async_create_cync(hass, entry)

    devices_coordinator = CyncCoordinator(hass, entry, cync)

    cync.set_update_callback(devices_coordinator.on_data_update)

    await devices_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = devices_coordinator

    _migrate_unique_ids(hass, entry, cync)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Unload a config entry."""
    cync = entry.runtime_data.cync
    await cync.shut_down()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
