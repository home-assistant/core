""" Support for Wink sensors. """
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.wink.pywink as pywink

from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_ACCESS_TOKEN, STATE_OPEN, STATE_CLOSED


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


class WinkSensorDevice(Entity):
    """ represents a wink sensor within home assistant. """

    def __init__(self, wink):
        self.wink = wink

    @property
    def state(self):
        """ Returns the state. """
        return STATE_OPEN if self.is_open else STATE_CLOSED

    @property
    def unique_id(self):
        """ Returns the id of this wink sensor """
        return "{}.{}".format(self.__class__, self.wink.deviceId())

    @property
    def name(self):
        """ Returns the name of the sensor if any. """
        return self.wink.name()

    def update(self):
        """ Update state of the sensor. """
        self.wink.updateState()

    @property
    def is_open(self):
        """ True if door is open. """
        return self.wink.state()
