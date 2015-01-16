""" Support for WeMo switchces. """
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.wink.pywink as pywink

from homeassistant.components.wink import WinkToggleDevice
from homeassistant.const import CONF_ACCESS_TOKEN


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Wink switches. """
    token = config.get(CONF_ACCESS_TOKEN)

    if token is None:
        logging.getLogger(__name__).error(
            "Missing wink access_token - "
            "get one at https://winkbearertoken.appspot.com/")
        return []

    pywink.set_bearer_token(token)

    return get_switches()


# pylint: disable=unused-argument
def devices_discovered(hass, config, info):
    """ Called when a device is discovered. """
    return get_switches()


def get_switches():
    """ Returns the Wink switches. """
    return [WinkToggleDevice(switch) for switch in pywink.get_switches()]
