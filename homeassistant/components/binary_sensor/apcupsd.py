"""
homeassistant.components.binary_sensor.apcupsd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides a binary sensor to track online status of a UPS.
"""
from homeassistant.core import JobPriority
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components import apcupsd


DEPENDENCIES = [apcupsd.DOMAIN]

DEFAULT_NAME = "UPS Online Status"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """ Instantiate an OnlineStatus binary sensor entity and add it to HA. """
    add_entities((OnlineStatus(hass, config),))


class OnlineStatus(BinarySensorDevice):
    """ Binary sensor to represent UPS online status. """
    def __init__(self, hass, config):
        self._config = config
        self._state = None
        # Get initial state
        hass.pool.add_job(
            JobPriority.EVENT_STATE, (self.update_ha_state, True))

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
        Get the latest status report from APCUPSd and establish whether the
        UPS is online.
        """
        status = apcupsd.GET_STATUS()
        self._state = status[apcupsd.KEY_STATUS]
