"""
homeassistant.components.sensor.wink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Wink sensors.

For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/sensor.wink/
"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_ACCESS_TOKEN, STATE_OPEN, STATE_CLOSED

REQUIREMENTS = ['python-wink==0.4.2']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Wink platform. """
    import pywink

    if discovery_info is None:
        token = config.get(CONF_ACCESS_TOKEN)

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token. "
                "Get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    add_devices(WinkSensorDevice(sensor) for sensor in pywink.get_sensors())
    add_devices(WinkEggMinder(eggtray) for eggtray in pywink.get_eggtrays())


class WinkSensorDevice(Entity):
    """ Represents a Wink sensor. """

    def __init__(self, wink):
        self.wink = wink

    @property
    def state(self):
        """ Returns the state. """
        return STATE_OPEN if self.is_open else STATE_CLOSED

    @property
    def unique_id(self):
        """ Returns the id of this wink sensor """
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """ Returns the name of the sensor if any. """
        return self.wink.name()

    def update(self):
        """ Update state of the sensor. """
        self.wink.update_state()

    @property
    def is_open(self):
        """ True if door is open. """
        return self.wink.state()


class WinkEggMinder(Entity):
    """ Represents a Wink Egg Minder. """

    def __init__(self, wink):
        self.wink = wink

    @property
    def state(self):
        """ Returns the state. """
        return self.wink.state()

    @property
    def unique_id(self):
        """ Returns the id of this wink Egg Minder """
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """ Returns the name of the Egg Minder if any. """
        return self.wink.name()

    def update(self):
        """ Update state of the Egg Minder. """
        self.wink.update_state()
