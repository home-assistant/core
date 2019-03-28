"""
Support for the GPSLogger platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.gpslogger/
"""
import logging

from homeassistant.components.gpslogger import TRACKER_UPDATE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType, ConfigType

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['gpslogger']


async def async_setup_scanner(hass: HomeAssistantType, config: ConfigType,
                              async_see, discovery_info=None):
    """Set up an endpoint for the GPSLogger device tracker."""
    async def _set_location(device, gps_location, battery, accuracy, attrs):
        """Fire HA event to set location."""
        await async_see(
            dev_id=device,
            gps=gps_location,
            battery=battery,
            gps_accuracy=accuracy,
            attributes=attrs
        )

    async_dispatcher_connect(hass, TRACKER_UPDATE, _set_location)
    return True
