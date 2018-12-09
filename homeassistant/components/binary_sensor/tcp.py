"""
Provides a binary sensor which gets its values from a TCP socket.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.tcp/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.sensor.tcp import (
    TcpSensor, CONF_VALUE_ON, PLATFORM_SCHEMA)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the TCP binary sensor."""
    add_entities([TcpBinarySensor(hass, config)])


class TcpBinarySensor(BinarySensorDevice, TcpSensor):
    """A binary sensor which is on when its state == CONF_VALUE_ON."""

    required = (CONF_VALUE_ON,)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state == self._config[CONF_VALUE_ON]
