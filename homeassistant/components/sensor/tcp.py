"""
homeassistant.components.sensor.tcp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides a sensor which gets its values from a TCP socket.
"""
import logging

from homeassistant.components import tcp


DEPENDENCIES = [tcp.DOMAIN]

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """ Create the Sensor. """
    if not tcp.TCPEntity.validate_config(config):
        return False
    add_entities((tcp.TCPEntity(config),))
