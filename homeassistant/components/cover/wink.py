"""
Support for Wink Covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.wink/
"""
import logging

from homeassistant.components.cover import CoverDevice
from homeassistant.components.wink import WinkDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['python-wink==0.7.13', 'pubnub==3.8.2']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink cover platform."""
    import pywink

    if discovery_info is None:
        token = config.get(CONF_ACCESS_TOKEN)

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token. "
                "Get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    add_devices(WinkCoverDevice(shade) for shade, door in
                pywink.get_shades())


class WinkCoverDevice(WinkDevice, CoverDevice):
    """Representation of a Wink covers."""

    def __init__(self, wink):
        """Initialize the cover."""
        WinkDevice.__init__(self, wink)

    @property
    def should_poll(self):
        """Wink Shades don't track their position."""
        return False

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
