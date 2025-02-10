"""The Hunter Douglas PowerView integration."""

import logging
from typing import TYPE_CHECKING

from aiopvapi.resources.model import PowerviewData
from aiopvapi.rooms import Rooms
from aiopvapi.scenes import Scenes
from aiopvapi.shades import Shades

from homeassistant.const import CONF_API_VERSION, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, HUB_EXCEPTIONS
from .coordinator import PowerviewShadeUpdateCoordinator
from .model import PowerviewConfigEntry, PowerviewEntryData
from .shade_data import PowerviewShadeData
from .util import async_connect_hub

PARALLEL_UPDATES = 1


PLATFORMS = [
    Platform.BUTTON,
    Platform.COVER,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SELECT,
    Platform.SENSOR,
]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: PowerviewConfigEntry) -> bool:
    """Set up Hunter Douglas PowerView from a config entry."""
    config = entry.data
    hub_address: str = config[CONF_HOST]
    api_version: int | None = config.get(CONF_API_VERSION)
    _LOGGER.debug("Connecting %s at %s with v%s api", DOMAIN, hub_address, api_version)

    # default 15 second timeout for each call in upstream
    try:
        api = await async_connect_hub(hass, hub_address, api_version)
    except HUB_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            f"Connection error to PowerView hub {hub_address}: {err}"
        ) from err

    hub = api.hub
    pv_request = api.pv_request
    device_info = api.device_info

    if hub.role != "Primary":
        # this should be caught in config_flow, but account for a hub changing roles
        # this will only happen manually by a user
        _LOGGER.error(
            "%s (%s) is performing role of %s Hub. "
            "Only the Primary Hub can manage shades",
            hub.name,
            hub.hub_address,
            hub.role,
        )
        return False

    try:
        rooms = Rooms(pv_request)
        room_data: PowerviewData = await rooms.get_rooms()

        scenes = Scenes(pv_request)
        scene_data: PowerviewData = await scenes.get_scenes()

        shades = Shades(pv_request)
        shade_data: PowerviewData = await shades.get_shades()
    except HUB_EXCEPTIONS as err:
        raise ConfigEntryNotReady(
            f"Connection error to PowerView hub {hub_address}: {err}"
        ) from err

    if not device_info:
        raise ConfigEntryNotReady(f"Unable to initialize PowerView hub: {hub_address}")

    if CONF_API_VERSION not in config:
        new_data = {**entry.data}
        new_data[CONF_API_VERSION] = hub.api_version
        hass.config_entries.async_update_entry(entry, data=new_data)

    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=device_info.serial_number
        )

    coordinator = PowerviewShadeUpdateCoordinator(hass, entry, shades, hub)
    coordinator.async_set_updated_data(PowerviewShadeData())
    # populate raw shade data into the coordinator for diagnostics
    coordinator.data.store_group_data(shade_data)

    entry.runtime_data = PowerviewEntryData(
        api=pv_request,
        room_data=room_data.processed,
        scene_data=scene_data.processed,
        shade_data=shade_data.processed,
        coordinator=coordinator,
        device_info=device_info,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: PowerviewConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: PowerviewConfigEntry) -> bool:
    """Migrate entry."""

    _LOGGER.debug("Migrating from version %s.%s", entry.version, entry.minor_version)

    if entry.version == 1:
        # 1 -> 2: Unique ID from integer to string
        if entry.minor_version == 1:
            if entry.unique_id is None:
                await _async_add_missing_entry_unique_id(hass, entry)
            await _migrate_unique_ids(hass, entry)
            hass.config_entries.async_update_entry(entry, minor_version=2)

    _LOGGER.debug("Migrated to version %s.%s", entry.version, entry.minor_version)

    return True


async def _async_add_missing_entry_unique_id(
    hass: HomeAssistant, entry: PowerviewConfigEntry
) -> None:
    """Add the unique id if its missing."""
    address: str = entry.data[CONF_HOST]
    api_version: int | None = entry.data.get(CONF_API_VERSION)
    api = await async_connect_hub(hass, address, api_version)
    hass.config_entries.async_update_entry(
        entry, unique_id=api.device_info.serial_number
    )


async def _migrate_unique_ids(hass: HomeAssistant, entry: PowerviewConfigEntry) -> None:
    """Migrate int based unique ids to str."""
    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    if TYPE_CHECKING:
        assert entry.unique_id
    for reg_entry in registry_entries:
        if isinstance(reg_entry.unique_id, int) or (
            isinstance(reg_entry.unique_id, str)
            and not reg_entry.unique_id.startswith(entry.unique_id)
        ):
            _LOGGER.debug(
                "Migrating %s: %s to %s_%s",
                reg_entry.entity_id,
                reg_entry.unique_id,
                entry.unique_id,
                reg_entry.unique_id,
            )
            entity_registry.async_update_entity(
                reg_entry.entity_id,
                new_unique_id=f"{entry.unique_id}_{reg_entry.unique_id}",
            )
