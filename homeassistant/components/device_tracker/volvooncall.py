"""
Support for tracking a Volvo.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/device_tracker.volvooncall/
"""
import logging

from homeassistant.util import slugify
from homeassistant.components.volvooncall import DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_scanner(hass, config, see, discovery_info=None):
    """Set up the Volvo tracker."""
    if discovery_info is None:
        return

    vin, _ = discovery_info
    vehicle = hass.data[DOMAIN].vehicles[vin]

    host_name = vehicle.registration_number
    dev_id = 'volvo_' + slugify(host_name)

    def see_vehicle(vehicle):
        """Handle the reporting of the vehicle position."""
        see(dev_id=dev_id,
            host_name=host_name,
            gps=(vehicle.position['latitude'],
                 vehicle.position['longitude']))

    hass.data[DOMAIN].entities[vin].append(see_vehicle)
    see_vehicle(vehicle)

    return True
