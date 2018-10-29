"""
Support for the Geofency platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.geofency/
"""
import logging
from functools import partial

from homeassistant.components.geofency import TRACKER_UPDATE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['geofency']


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Geofency device tracker."""
    @callback
    def _set_location(device, gps, location_name, attributes):
        """Fire HA event to set location."""
        hass.async_add_job(
            partial(
                see,
                dev_id=device,
                gps=gps,
                location_name=location_name,
                attributes=attributes
            )
        )

    async_dispatcher_connect(hass, TRACKER_UPDATE, _set_location)
    return True
