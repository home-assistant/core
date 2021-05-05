"""The flunearyou component."""
import asyncio
from datetime import timedelta
from functools import partial

from pyflunearyou import Client
from pyflunearyou.errors import FluNearYouError

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CATEGORY_CDC_REPORT,
    CATEGORY_USER_REPORT,
    DATA_COORDINATOR,
    DOMAIN,
    LOGGER,
)

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=30)

CONFIG_SCHEMA = cv.deprecated(DOMAIN)

PLATFORMS = ["sensor"]


async def async_setup(hass, config):
    """Set up the Flu Near You component."""
    hass.data[DOMAIN] = {DATA_COORDINATOR: {}}
    return True


async def async_setup_entry(hass, entry):
    """Set up Flu Near You as config entry."""
    hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id] = {}

    websession = aiohttp_client.async_get_clientsession(hass)
    client = Client(websession)

    latitude = entry.data.get(CONF_LATITUDE, hass.config.latitude)
    longitude = entry.data.get(CONF_LONGITUDE, hass.config.longitude)

    async def async_update(api_category):
        """Get updated date from the API based on category."""
        try:
            if api_category == CATEGORY_CDC_REPORT:
                return await client.cdc_reports.status_by_coordinates(
                    latitude, longitude
                )
            return await client.user_reports.status_by_coordinates(latitude, longitude)
        except FluNearYouError as err:
            raise UpdateFailed(err) from err

    data_init_tasks = []
    for api_category in [CATEGORY_CDC_REPORT, CATEGORY_USER_REPORT]:
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR][entry.entry_id][
            api_category
        ] = DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{api_category} ({latitude}, {longitude})",
            update_interval=DEFAULT_UPDATE_INTERVAL,
            update_method=partial(async_update, api_category),
        )
        data_init_tasks.append(coordinator.async_refresh())

    await asyncio.gather(*data_init_tasks)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass, entry):
    """Unload an Flu Near You config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATOR].pop(entry.entry_id)

    return unload_ok
