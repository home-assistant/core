"""
Provides a binary sensor which gets its values from a TCP socket.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.tcp/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.sensor.tcp import Sensor, CONF_VALUE_ON


_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Create the binary sensor."""
    if not BinarySensor.validate_config(config):
        return False

    add_entities((BinarySensor(hass, config),))


class BinarySensor(BinarySensorDevice, Sensor):
    """A binary sensor which is on when its state == CONF_VALUE_ON."""

    required = (CONF_VALUE_ON,)

    @property
    def is_on(self):
        """True if the binary sensor is on."""
        return self._state == self._config[CONF_VALUE_ON]
