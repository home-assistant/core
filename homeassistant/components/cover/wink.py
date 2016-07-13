"""
Support for Wink covers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/cover.wink/
"""
import logging

from homeassistant.components.cover import CoverDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['python-wink==0.7.8']


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

    add_devices(WinkCoverDevice(cover) for cover in pywink.get_garage_doors())


class WinkCoverDevice(CoverDevice):
    """Representation of a Wink cover."""

    def __init__(self, wink):
        """Initialize the cover."""
        self.wink = wink

    @property
    def unique_id(self):
        """Return the ID of this wink cover."""
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the cover if any."""
        return self.wink.name()

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self.wink.state() == 0

    @property
    def available(self):
        """True if connection == True."""
        return self.wink.available

    def update(self):
        """Update the state of the cover."""
        self.wink.update_state()

    def open_cover(self):
        """Open the cover."""
        self.wink.set_state(1)

    def close_cover(self):
        """Close the cover."""
        self.wink.set_state(0)

    def stop_cover(self):
        """Wink is not able to stop covers."""
        pass
