"""Provides a binary sensor which gets its values from a TCP socket."""
from homeassistant.components.binary_sensor import BinarySensorEntity

from .sensor import CONF_VALUE_ON, PLATFORM_SCHEMA, TcpSensor

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the TCP binary sensor."""
    add_entities([TcpBinarySensor(hass, config)])


class TcpBinarySensor(BinarySensorEntity, TcpSensor):
    """A binary sensor which is on when its state == CONF_VALUE_ON."""

    required = (CONF_VALUE_ON,)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state == self._config[CONF_VALUE_ON]
