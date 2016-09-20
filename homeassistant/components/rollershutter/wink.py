"""
Support for Wink Shades.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/rollershutter.wink/
"""

from homeassistant.components.rollershutter import RollershutterDevice
from homeassistant.components.wink import WinkDevice

DEPENDENCIES = ['wink']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink rollershutter platform."""
    import pywink

    add_devices(WinkRollershutterDevice(shade) for shade in
                pywink.get_shades())


# pylint: disable=abstract-method
class WinkRollershutterDevice(WinkDevice, RollershutterDevice):
    """Representation of a Wink rollershutter (shades)."""

    def __init__(self, wink):
        """Initialize the rollershutter."""
        WinkDevice.__init__(self, wink)

    @property
    def should_poll(self):
        """Wink Shades don't track their position."""
        return False

    def move_down(self):
        """Close the shade."""
        self.wink.set_state(0)

    def move_up(self):
        """Open the shade."""
        self.wink.set_state(1)

    @property
    def current_position(self):
        """Return current position of roller shutter.

        Wink reports blind shade positions as 0 or 1.
        home-assistant expects:
        None is unknown, 0 is closed, 100 is fully open.
        """
        state = self.wink.state()
        if state == 0:
            return 0
        elif state == 1:
            return 100
        else:
            return None

    def stop(self):
        """Can't stop Wink rollershutter due to API."""
        pass
