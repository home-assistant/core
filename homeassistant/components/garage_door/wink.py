"""
Support for Wink garage doors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/garage_door.wink/
"""
import logging

from homeassistant.components.garage_door import GarageDoorDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['python-wink==0.6.2']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Sets up the Wink garage door platform."""
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


class WinkGarageDoorDevice(GarageDoorDevice):
    """Represents a Wink garage door."""

    def __init__(self, wink):
        self.wink = wink

    @property
    def unique_id(self):
        """Returns the id of this wink garage door."""
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Returns the name of the garage door if any."""
        return self.wink.name()

    def update(self):
        """Update the state of the garage door."""
        self.wink.update_state()

    @property
    def is_closed(self):
        """Returns true if door is closed."""
        return self.wink.state() == 0

    def close_door(self):
        """Closes the door."""
        self.wink.set_state(0)

    def open_door(self):
        """Open the door."""
        self.wink.set_state(1)
