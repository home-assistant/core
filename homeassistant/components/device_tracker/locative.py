"""
Support for the Locative platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.locative/
"""
import logging

from homeassistant.components.locative import TRACKER_UPDATE
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['locative']


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Set up an endpoint for the Locative device tracker."""
    async def _set_location(device, gps_location, location_name):
        """Fire HA event to set location."""
        await async_see(
            dev_id=device,
            gps=gps_location,
            location_name=location_name
        )

    async_dispatcher_connect(hass, TRACKER_UPDATE, _set_location)
    return True
