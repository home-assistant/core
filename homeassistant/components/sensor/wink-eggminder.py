"""
homeassistant.components.egg_minder.wink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Wink Egg Minder.
For more details about this platform, please refer to the documentation at
at https://home-assistant.io/components/sensor.wink-eggminder/
"""
import logging

from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['https://github.com/balloob/python-wink/archive/'
                'e66277ddb8ba51df34e810f784088c3c8582984a.zip'
                '#python-wink==0.2.1']

def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Wink platform. """
    import pywink

    if discovery_info is None:
        token = config.get('access_token')

        if token is None:
            logging.getLogger(__name__).error(
                "Missing wink access_token. "
                "Get one at https://winkbearertoken.appspot.com/")
            return

        pywink.set_bearer_token(token)

    add_devices(WinkEggMinder(eggtray) for eggtray in pywink.get_eggtrays())


class WinkEggMinder(Entity):
    """ Represents a Wink sensor. """

    def __init__(self, wink):
        self.wink = wink

    @property
    def state(self):
        """ Returns the state. """
        return self.wink.state()

    @property
    def unique_id(self):
        """ Returns the id of this wink sensor """
        return "{}.{}".format(self.__class__, self.wink.deviceId())

    @property
    def name(self):
        """ Returns the name of the sensor if any. """
        return self.wink.name()

    def update(self):
      """ Update state of the Egg Minder. """
      self.wink.updateState()

    #@property
    #def egg_count(self):
    #    """ The number of eggs """
    #    return self.wink.state()
