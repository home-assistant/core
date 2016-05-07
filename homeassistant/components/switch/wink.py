"""
Support for Wink switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wink/
"""
import logging

from homeassistant.components.wink import WinkToggleDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['python-wink==0.7.6']


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
