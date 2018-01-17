"""
Support for Mercedes cars with Mercedes ME.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mercedesme/
"""
import logging
from homeassistant.helpers.event import track_utc_time_change

_LOGGER = logging.getLogger(__name__)

DATA_MME = 'mercedesme'


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Mercedes ME tracker."""
    if discovery_info is None:
        return

    controller = hass.data[DATA_MME]['controller']

    if not controller.cars:
        return

    MercedesMEDeviceTracker(hass, config, see, controller)


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
            location = self.controller.get_location(device["vin"])
            if location is None:
                return
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
