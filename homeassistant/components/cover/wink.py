"""
Support for Wink Covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.wink/
"""

from homeassistant.components.cover import CoverDevice
from homeassistant.components.wink import WinkDevice

DEPENDENCIES = ['wink']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink cover platform."""
    import pywink

    add_devices(WinkCoverDevice(shade) for shade in
                pywink.get_shades())
    add_devices(WinkCoverDevice(door) for door in
                pywink.get_garage_doors())


class WinkCoverDevice(WinkDevice, CoverDevice):
    """Representation of a Wink cover device."""

    def __init__(self, wink):
        """Initialize the cover."""
        WinkDevice.__init__(self, wink)

    def close_cover(self):
        """Close the shade."""
        self.wink.set_state(0)

    def open_cover(self):
        """Open the shade."""
        self.wink.set_state(1)

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        state = self.wink.state()
        if state == 0:
            return True
        elif state == 1:
            return False
        else:
            return None
