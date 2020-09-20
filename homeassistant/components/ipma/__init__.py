"""Component for the Portuguese weather service - IPMA."""
import asyncio
import logging

import async_timeout
from pyipma.api import IPMA_API as ipma_api
from pyipma.location import Location

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .config_flow import IpmaFlowHandler  # noqa: F401
from .const import DOMAIN, IPMA_API, IPMA_LOCATION  # noqa: F401

DEFAULT_NAME = "ipma"

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "weather"]


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured IPMA."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up IPMA station as config entry."""
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]

    websession = async_get_clientsession(hass)
    api = ipma_api(websession)

    with async_timeout.timeout(30):
        location = await Location.get(api, float(latitude), float(longitude))

    _LOGGER.debug(
        "Initializing for coordinates %s, %s -> station %s (%d, %d)",
        latitude,
        longitude,
        location.station,
        location.id_station,
        location.global_id_local,
    )

    ipma_hass_data = hass.data.setdefault(DOMAIN, {})
    ipma_hass_data[config_entry.entry_id] = {
        IPMA_API: api,
        IPMA_LOCATION: location,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
