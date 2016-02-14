"""
homeassistant.components.binary_sensor.tcp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides a binary_sensor which gets its values from a TCP socket.
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components import tcp


DEPENDENCIES = [tcp.DOMAIN]

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """ Create the BinarySensor. """
    if not BinarySensor.validate_config(config):
        return False
    add_entities((BinarySensor(config),))


class BinarySensor(tcp.TCPEntity, BinarySensorDevice):
    """ A binary sensor which is on when its state == CONF_VALUE_ON. """
    required = (tcp.CONF_VALUE_ON,)

    @property
    def is_on(self):
        return self._state == self._config[tcp.CONF_VALUE_ON]
