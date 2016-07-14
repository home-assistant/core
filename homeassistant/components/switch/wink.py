"""
Support for Wink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wink/
"""
import logging

from homeassistant.components.wink import WinkDevice
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.entity import ToggleEntity

REQUIREMENTS = ['python-wink==0.7.10', 'pubnub==3.8.2']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Wink platform."""
    import pywink

    if discovery_info is None:
        token = config.get(CONF_ACCESS_TOKEN)

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token. "
                "Get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    add_devices(WinkToggleDevice(switch) for switch in pywink.get_switches())
    add_devices(WinkToggleDevice(switch) for switch in
                pywink.get_powerstrip_outlets())
    add_devices(WinkToggleDevice(switch) for switch in pywink.get_sirens())


class WinkToggleDevice(WinkDevice, ToggleEntity):
    """Represents a Wink toggle (switch) device."""

    def __init__(self, wink):
        """Initialize the Wink device."""
        WinkDevice.__init__(self, wink)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.wink.state()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.wink.set_state(True)

    def turn_off(self):
        """Turn the device off."""
        self.wink.set_state(False)
