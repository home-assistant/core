"""
Support for Wink garage doors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/garage_door.wink/
"""
import logging

from homeassistant.components.garage_door import GarageDoorDevice
from homeassistant.components.wink import WinkDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['python-wink==0.7.10', 'pubnub==3.8.2']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink garage door platform."""
    import pywink

    if discovery_info is None:
        token = config.get(CONF_ACCESS_TOKEN)

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token. "
                "Get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    add_devices(WinkGarageDoorDevice(door) for door in
                pywink.get_garage_doors())


class WinkGarageDoorDevice(WinkDevice, GarageDoorDevice):
    """Representation of a Wink garage door."""

    def __init__(self, wink):
        """Initialize the garage door."""
        WinkDevice.__init__(self, wink)

    @property
    def is_closed(self):
        """Return true if door is closed."""
        return self.wink.state() == 0

    def close_door(self):
        """Close the door."""
        self.wink.set_state(0)

    def open_door(self):
        """Open the door."""
        self.wink.set_state(1)
