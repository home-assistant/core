"""The Tile component."""
import asyncio
from datetime import timedelta
from functools import partial

from pytile import async_login
from pytile.errors import SessionExpiredError, TileError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.async_ import gather_with_concurrency

from .const import DATA_COORDINATOR, DATA_TILE, DOMAIN, LOGGER

PLATFORMS = ["device_tracker"]
DEVICE_TYPES = ["PHONE", "TILE"]

DEFAULT_INIT_TASK_LIMIT = 2
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=2)

CONF_SHOW_INACTIVE = "show_inactive"


async def async_setup(hass, config):
    """Set up the Tile component."""
    hass.data[DOMAIN] = {DATA_COORDINATOR: {}, DATA_TILE: {}}
    return True


async def async_setup_entry(hass, entry):
    """Set up Tile as config entry."""
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = {}
    hass.data[DOMAIN][DATA_TILE][entry.entry_id] = {}

    websession = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await async_login(
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            session=websession,
        )
        hass.data[DOMAIN][DATA_TILE][entry.entry_id] = await client.async_get_tiles()
    except TileError as err:
        raise ConfigEntryNotReady("Error during integration setup") from err

    async def async_update_tile(tile):
        """Update the Tile."""
        try:
            return await tile.async_update()
        except SessionExpiredError:
            LOGGER.info("Tile session expired; creating a new one")
            await client.async_init()
        except TileError as err:
            raise UpdateFailed(f"Error while retrieving data: {err}") from err

    coordinator_init_tasks = []
    for tile_uuid, tile in hass.data[DOMAIN][DATA_TILE][entry.entry_id].items():
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
            tile_uuid
        ] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=tile.name,
            update_interval=DEFAULT_UPDATE_INTERVAL,
            update_method=partial(async_update_tile, tile),
        )
        coordinator_init_tasks.append(coordinator.async_refresh())

    await gather_with_concurrency(DEFAULT_INIT_TASK_LIMIT, *coordinator_init_tasks)

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload a Tile config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)

    return unload_ok
