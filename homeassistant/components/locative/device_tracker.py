"""Support for the Locative platform."""
import logging

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify

from . import DOMAIN as LOCATIVE_DOMAIN, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)

DATA_KEY = '{}.{}'.format(LOCATIVE_DOMAIN, DEVICE_TRACKER_DOMAIN)


async def async_setup_entry(hass, entry, async_see):
    """Configure a dispatcher connection based on a config entry."""
    async def _set_location(device, gps_location, location_name):
        """Fire HA event to set location."""
        await async_see(
            dev_id=slugify(device),
            gps=gps_location,
            location_name=location_name
        )

    hass.data[DATA_KEY] = async_dispatcher_connect(
        hass, TRACKER_UPDATE, _set_location
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload the config entry and remove the dispatcher connection."""
    hass.data[DATA_KEY]()
    return True
