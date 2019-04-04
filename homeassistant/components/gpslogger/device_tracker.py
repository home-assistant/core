"""Support for the GPSLogger device tracking."""
import logging

from homeassistant.components.device_tracker import (
    DOMAIN as DEVICE_TRACKER_DOMAIN)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN as GPSLOGGER_DOMAIN, TRACKER_UPDATE

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['gpslogger']

DATA_KEY = '{}.{}'.format(GPSLOGGER_DOMAIN, DEVICE_TRACKER_DOMAIN)


async def async_setup_entry(hass: HomeAssistantType, entry, async_see):
    """Configure a dispatcher connection based on a config entry."""
    async def _set_location(device, gps_location, battery, accuracy, attrs):
        """Fire HA event to set location."""
        await async_see(
            dev_id=device,
            gps=gps_location,
            battery=battery,
            gps_accuracy=accuracy,
            attributes=attrs
        )

    hass.data[DATA_KEY] = async_dispatcher_connect(
        hass, TRACKER_UPDATE, _set_location
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry):
    """Unload the config entry and remove the dispatcher connection."""
    hass.data[DATA_KEY]()
    return True
