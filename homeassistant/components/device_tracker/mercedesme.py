"""
Support for Mercedes cars with Mercedes ME.
"""
import logging
from homeassistant.helpers.event import track_utc_time_change

DOMAIN = 'mercedesme'

_LOGGER = logging.getLogger(__name__)

def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Mercedes ME tracker."""
    if discovery_info is None:
        return False

    controller = hass.data[DOMAIN]['controller']

    if not controller.cars:
        return False

    MercedesMEDeviceTracker(hass, config, see, controller)

    return True


class MercedesMEDeviceTracker(object):
    """A class representing a Mercedes ME device tracker."""

    def __init__(self, hass, config, see, controller):
        """Initialize the Mercedes ME device tracker."""
        self.hass = hass
        self.see = see
        self.controller = controller
        self.update_info()

        track_utc_time_change(
            self.hass, self.update_info, second=range(0, 60, 30))

    def update_info(self, now=None):
        """Update the device info."""
        for device in self.controller.cars:
            location = self.controller.getLocation(device["vin"])
            dev_id = device["vin"]
            name = device["license"]

            lat = location['positionLat']['value']
            lon = location['positionLong']['value']
            attrs = {
                'trackr_id': dev_id,
                'id': dev_id,
                'name': name
            }
            self.see(
                dev_id=dev_id, host_name=name,
                gps=(lat, lon), attributes=attrs
            )
