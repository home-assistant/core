""" Support for Wink sensors. """
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.wink.pywink as pywink

from homeassistant.components.wink import WinkSensorDevice
from homeassistant.const import CONF_ACCESS_TOKEN


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Wink sensors. """
    token = config.get(CONF_ACCESS_TOKEN)

    if token is None:
        logging.getLogger(__name__).error(
            "Missing wink access_token - "
            "get one at https://winkbearertoken.appspot.com/")
        return []

    pywink.set_bearer_token(token)

    return get_sensors()


# pylint: disable=unused-argument
def devices_discovered(hass, config, info):
    """ Called when a device is discovered. """
    return get_sensors()


def get_sensors():
    """ Returns the Wink sensors. """
    return [WinkSensorDevice(sensor) for sensor in pywink.get_sensors()]
