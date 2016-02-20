"""
homeassistant.components.binary_sensor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with binary sensors (sensors which only know two states)
that can be monitored.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor/
"""
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity import Entity
from homeassistant.const import (STATE_ON, STATE_OFF)
from homeassistant.components import (mysensors, )

DOMAIN = 'binary_sensor'
SCAN_INTERVAL = 30

ENTITY_ID_FORMAT = DOMAIN + '.{}'
SENSOR_CLASSES = [
    None,        # Generic on/off
    'opening',   # Door, window, etc
    'motion',    # Motion sensor
    'gas',       # CO, CO2, etc
    'smoke',     # Smoke detector
    'moisture',  # Specifically a wetness sensor
    'light',     # Lightness threshold
    'power',     # Power, over-current, etc
    'safety',    # Generic on=unsafe, off=safe
]

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
    mysensors.DISCOVER_BINARY_SENSORS: 'mysensors',
}


def setup(hass, config):
    """Track states and offer events for binary sensors."""
    component = EntityComponent(
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL,
        DISCOVERY_PLATFORMS)

    component.setup(config)

    return True


# pylint: disable=no-self-use
class BinarySensorDevice(Entity):
    """Represent a binary sensor."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return None

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def friendly_state(self):
        """Return the friendly state of the binary sensor."""
        return None

    @property
    def sensor_class(self):
        """Return the class of this sensor, from SENSOR_CASSES."""
        return None

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        return {
            'sensor_class': self.sensor_class,
        }
