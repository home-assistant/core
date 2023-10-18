"""The Tile component."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from functools import partial

from pytile import async_login
from pytile.errors import InvalidAuthError, SessionExpiredError, TileError
from pytile.tile import Tile

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.async_ import gather_with_limited_concurrency

from .const import DOMAIN, LOGGER

PLATFORMS = [Platform.DEVICE_TRACKER]
DEVICE_TYPES = ["PHONE", "TILE"]

DEFAULT_INIT_TASK_LIMIT = 2
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=2)

CONF_SHOW_INACTIVE = "show_inactive"


@dataclass
class TileData:
    """Define an object to be stored in `hass.data`."""

    coordinators: dict[str, DataUpdateCoordinator[None]]
    tiles: dict[str, Tile]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tile as config entry."""

    @callback
    def async_migrate_callback(entity_entry: RegistryEntry) -> dict | None:
        """Define a callback to migrate appropriate Tile entities to new unique IDs.

        Old: tile_{uuid}
        New: {username}_{uuid}
        """
        if entity_entry.unique_id.startswith(entry.data[CONF_USERNAME]):
            return None

        new_unique_id = f"{entry.data[CONF_USERNAME]}_".join(
            entity_entry.unique_id.split(f"{DOMAIN}_")
        )

        LOGGER.debug(
            "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
            entity_entry.entity_id,
            entity_entry.unique_id,
            new_unique_id,
        )

        return {"new_unique_id": new_unique_id}

    await async_migrate_entries(hass, entry.entry_id, async_migrate_callback)

    # Tile's API uses cookies to identify a consumer; in order to allow for multiple
    # instances of this config entry, we use a new session each time:
    websession = aiohttp_client.async_create_clientsession(hass)

    try:
        client = await async_login(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            session=websession,
        )
        tiles = await client.async_get_tiles()
    except InvalidAuthError as err:
        raise ConfigEntryAuthFailed("Invalid credentials") from err
    except TileError as err:
        raise ConfigEntryNotReady("Error during integration setup") from err

    async def async_update_tile(tile: Tile) -> None:
        """Update the Tile."""
        try:
            await tile.async_update()
        except InvalidAuthError as err:
            raise ConfigEntryAuthFailed("Invalid credentials") from err
        except SessionExpiredError:
            LOGGER.info("Tile session expired; creating a new one")
            await client.async_init()
        except TileError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err

    coordinators: dict[str, DataUpdateCoordinator[None]] = {}
    coordinator_init_tasks = []

    for tile_uuid, tile in tiles.items():
        coordinator = coordinators[tile_uuid] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=tile.name,
            update_interval=DEFAULT_UPDATE_INTERVAL,
            update_method=partial(async_update_tile, tile),
        )
        coordinator_init_tasks.append(coordinator.async_refresh())

    await gather_with_limited_concurrency(
        DEFAULT_INIT_TASK_LIMIT, *coordinator_init_tasks
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = TileData(coordinators=coordinators, tiles=tiles)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Tile config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
