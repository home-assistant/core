"""The Recollect Waste integration."""
import asyncio
from datetime import date, timedelta
from typing import List

from aiorecollect.client import Client, PickupEvent
from aiorecollect.errors import RecollectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, DATA_COORDINATOR, DOMAIN, LOGGER

DEFAULT_NAME = "recollect_waste"
DEFAULT_UPDATE_INTERVAL = timedelta(days=1)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the RainMachine component."""
    hass.data[DOMAIN] = {DATA_COORDINATOR: {}}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RainMachine as config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = Client(
        entry.data[CONF_PLACE_ID], entry.data[CONF_SERVICE_ID], session=session
    )

    async def async_get_pickup_events() -> List[PickupEvent]:
        """Get the next pickup."""
        try:
            return await client.async_get_pickup_events(
                start_date=date.today(), end_date=date.today() + timedelta(weeks=4)
            )
        except RecollectError as err:
            raise UpdateFailed(
                f"Error while requesting data from Recollect: {err}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"Place {entry.data[CONF_PLACE_ID]}, Service {entry.data[CONF_SERVICE_ID]}",
        update_interval=DEFAULT_UPDATE_INTERVAL,
        update_method=async_get_pickup_events,
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = coordinator

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an RainMachine config entry."""
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
