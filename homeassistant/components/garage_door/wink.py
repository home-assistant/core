"""
Support for Wink garage doors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/garage_door.wink/
"""
import logging

from homeassistant.components.garage_door import GarageDoorDevice
from homeassistant.const import CONF_ACCESS_TOKEN, ATTR_BATTERY_LEVEL

REQUIREMENTS = ['python-wink==0.7.6']


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


class WinkGarageDoorDevice(GarageDoorDevice):
    """Representation of a Wink garage door."""

    def __init__(self, wink):
        """Initialize the garage door."""
        self.wink = wink
        self._battery = self.wink.battery_level

    @property
    def unique_id(self):
        """Return the ID of this wink garage door."""
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the garage door if any."""
        return self.wink.name()

    def update(self):
        """Update the state of the garage door."""
        self.wink.update_state()

    @property
    def is_closed(self):
        """Return true if door is closed."""
        return self.wink.state() == 0

    @property
    def available(self):
        """True if connection == True."""
        return self.wink.available

    def close_door(self):
        """Close the door."""
        self.wink.set_state(0)

    def open_door(self):
        """Open the door."""
        self.wink.set_state(1)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._battery:
            return {
                ATTR_BATTERY_LEVEL: self._battery_level,
            }

    @property
    def _battery_level(self):
        """Return the battery level."""
        return self.wink.battery_level * 100
