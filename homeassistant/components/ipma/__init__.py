"""Component for the Portuguese weather service - IPMA."""
import logging

import async_timeout
from pyipma import IPMAException
from pyipma.api import IPMA_API
from pyipma.location import Location

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_flow import IpmaFlowHandler  # noqa: F401
from .const import DATA_API, DATA_LOCATION, DOMAIN

DEFAULT_NAME = "ipma"

PLATFORMS = [Platform.WEATHER]

_LOGGER = logging.getLogger(__name__)


async def async_get_api(hass):
    """Get the pyipma api object."""
    websession = async_get_clientsession(hass)
    return IPMA_API(websession)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up IPMA station as config entry."""

    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]

    api = await async_get_api(hass)
    try:
        async with async_timeout.timeout(30):
            location = await Location.get(api, float(latitude), float(longitude))

        _LOGGER.debug(
            "Initializing for coordinates %s, %s -> station %s (%d, %d)",
            latitude,
            longitude,
            location.station,
            location.id_station,
            location.global_id_local,
        )
    except IPMAException as err:
        raise ConfigEntryNotReady(
            f"Could not get location for ({latitude},{longitude})"
        ) from err

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = {DATA_API: api, DATA_LOCATION: location}

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
