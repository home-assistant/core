"""
homeassistant.components.binary_sensor.apcupsd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides a binary sensor to track online status of a UPS.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.apcupsd/
"""
from homeassistant.components import apcupsd
from homeassistant.components.binary_sensor import BinarySensorDevice

DEPENDENCIES = [apcupsd.DOMAIN]
DEFAULT_NAME = "UPS Online Status"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """ Instantiate an OnlineStatus binary sensor entity and add it to HA. """
    add_entities((OnlineStatus(config, apcupsd.DATA),))


class OnlineStatus(BinarySensorDevice):
    """ Binary sensor to represent UPS online status. """
    def __init__(self, config, data):
        self._config = config
        self._data = data
        self._state = None
        self.update()

    @property
    def name(self):
        """ The name of the UPS online status sensor. """
        return self._config.get("name", DEFAULT_NAME)

    @property
    def is_on(self):
        """ True if the UPS is online, else False. """
        return self._state == apcupsd.VALUE_ONLINE

    def update(self):
        """
        Get the status report from APCUPSd (or cache) and set this entity's
        state.
        """
        self._state = self._data.status[apcupsd.KEY_STATUS]
