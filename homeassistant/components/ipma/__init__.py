"""Component for the Portuguese weather service - IPMA."""

import asyncio
from dataclasses import dataclass
import logging

from pyipma import IPMAException
from pyipma.api import IPMA_API
from pyipma.location import Location

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_flow import IpmaFlowHandler  # noqa: F401

DEFAULT_NAME = "ipma"

PLATFORMS = [Platform.SENSOR, Platform.WEATHER]

_LOGGER = logging.getLogger(__name__)

type IpmaConfigEntry = ConfigEntry[IpmaRuntimeData]


@dataclass
class IpmaRuntimeData:
    """IPMA runtime data."""

    api: IPMA_API
    location: Location


async def async_setup_entry(hass: HomeAssistant, config_entry: IpmaConfigEntry) -> bool:
    """Set up IPMA station as config entry."""

    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]

    api = IPMA_API(async_get_clientsession(hass))

    try:
        async with asyncio.timeout(30):
            location = await Location.get(api, float(latitude), float(longitude))
    except (IPMAException, TimeoutError) as err:
        raise ConfigEntryNotReady(
            f"Could not get location for ({latitude},{longitude})"
        ) from err

    _LOGGER.debug(
        "Initializing for coordinates %s, %s -> station %s (%d, %d)",
        latitude,
        longitude,
        location.station,
        location.id_station,
        location.global_id_local,
    )

    config_entry.runtime_data = IpmaRuntimeData(api=api, location=location)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IpmaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
