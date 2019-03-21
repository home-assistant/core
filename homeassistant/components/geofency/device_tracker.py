"""
Support for the Geofency device tracker platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.geofency/
"""
import logging

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN as GEOFENCY_DOMAIN, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['geofency']

DATA_KEY = '{}.{}'.format(GEOFENCY_DOMAIN, DEVICE_TRACKER_DOMAIN)


async def async_setup_entry(hass, entry, async_see):
    """Configure a dispatcher connection based on a config entry."""
    async def _set_location(device, gps, location_name, attributes):
        """Fire HA event to set location."""
        await async_see(
            dev_id=device,
            gps=gps,
            location_name=location_name,
            attributes=attributes
        )

    hass.data[DATA_KEY] = async_dispatcher_connect(
        hass, TRACKER_UPDATE, _set_location
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload the config entry and remove the dispatcher connection."""
    hass.data[DATA_KEY]()
    return True
