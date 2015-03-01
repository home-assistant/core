""" Support for Wink sensors. """
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.wink.pywink as pywink

from homeassistant.components.wink import WinkSensorDevice
from homeassistant.const import CONF_ACCESS_TOKEN


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Wink platform. """
    if discovery_info is None:
        token = config.get(CONF_ACCESS_TOKEN)

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token - "
                "get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    add_devices(WinkSensorDevice(sensor) for sensor in pywink.get_sensors())
