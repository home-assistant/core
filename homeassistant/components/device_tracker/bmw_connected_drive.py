"""Device tracker for BMW Connected Drive vehicles.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.bmw_connected_drive/
"""
import logging

from homeassistant.components.bmw_connected_drive import DOMAIN \
    as BMW_DOMAIN
from homeassistant.helpers.event import track_utc_time_change
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['bmw_connected_drive']


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the BMW tracker."""
    vehicles = hass.data[BMW_DOMAIN]
    _LOGGER.debug('Found BME vehicles: %s',
                  ', '.join([v.name for v in vehicles]))
    for vehicle in vehicles:
        BMWDeviceTracker(hass, see, vehicle)
    return True


class BMWDeviceTracker(object):
    """A class representing a BMW device tracker."""

    def __init__(self, hass, see, vehicle):
        """Initialize the Tracker."""
        self._see = see
        self._vehicle = vehicle
        self._update_info()

        track_utc_time_change(
            hass, self._update_info, second=range(0, 60, 30))

    def _update_info(self, now=None):
        """Update the device info."""
        dev_id = slugify(self._vehicle.name)
        attrs = {
            'trackr_id': dev_id,
            'id': dev_id,
            'name': self._vehicle.name
        }
        self._see(
            dev_id=dev_id, host_name=self._vehicle.name,
            gps=self._vehicle.bimmer.gps_position, attributes=attrs,
            icon='mdi:car'
        )
