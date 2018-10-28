"""
Support for Fibaro sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fibaro/
"""
import logging
from datetime import timedelta

from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.fibaro import (
    FIBARO_CONTROLLER, FIBARO_DEVICES, FibaroDevice)

DEPENDENCIES = ['fibaro']

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Fibaro controller devices."""
    add_entities(
        [FibaroSensor(device, hass.data[FIBARO_CONTROLLER])
         for device in hass.data[FIBARO_DEVICES]['sensor']], True)


class FibaroSensor(FibaroDevice, Entity):
    """Representation of a Fibaro Sensor."""

    def __init__(self, fibaro_device, controller):
        """Initialize the sensor."""
        self.current_value = None
        self.last_changed_time = None
        FibaroDevice.__init__(self, fibaro_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    @property
    def state(self):
        """Return the name of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        try:
            if self.fibaro_device.type == 'com.fibaro.humiditySensor':
                return '%'
            if self.fibaro_device.properties.unit == 'lux':
                return 'lx'
            if self.fibaro_device.properties.unit == 'C':
                return TEMP_CELSIUS
            if self.fibaro_device.properties.unit == 'F':
                return TEMP_FAHRENHEIT
            return self.fibaro_device.properties.unit
        except KeyError:
            pass
        except ValueError:
            pass
        return 'level'

    def update(self):
        """Update the state."""
        try:
            self.current_value = self.fibaro_device.properties.value
        except ValueError:
            pass
