"""
homeassistant.components.switch.wink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for Wink switches.
"""
import logging

from homeassistant.components.wink import WinkToggleDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['https://github.com/balloob/python-wink/archive/'
                'c2b700e8ca866159566ecf5e644d9c297f69f257.zip'
                '#python-wink==0.1']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Wink platform. """
    import pywink

    if discovery_info is None:
        token = config.get(CONF_ACCESS_TOKEN)

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token - "
                "get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    add_devices(WinkToggleDevice(switch) for switch in pywink.get_switches())
