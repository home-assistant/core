"""
Support for VOC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.volvooncall/

"""
import logging
from math import floor

from homeassistant.components.volvooncall import (
    VolvoEntity, RESOURCES, CONF_SCANDINAVIAN_MILES)

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Volvo sensors."""
    if discovery_info is None:
        return
    add_devices([VolvoSensor(hass, *discovery_info)])


class VolvoSensor(VolvoEntity):
    """Representation of a Volvo sensor."""

    @property
    def state(self):
        """Return the state of the sensor."""
        val = getattr(self.vehicle, self._attribute)

        if val is None:
            return val

        if self._attribute == 'odometer':
            val /= 1000  # m -> km

        if 'mil' in self.unit_of_measurement:
            val /= 10  # km -> mil

        if self._attribute == 'average_fuel_consumption':
            val /= 10  # L/1000km -> L/100km
            if 'mil' in self.unit_of_measurement:
                return round(val, 2)
            else:
                return round(val, 1)
        elif self._attribute == 'distance_to_empty':
            return int(floor(val))
        else:
            return int(round(val))

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        unit = RESOURCES[self._attribute][3]
        if self._state.config[CONF_SCANDINAVIAN_MILES] and 'km' in unit:
            if self._attribute == 'average_fuel_consumption':
                return 'L/mil'
            else:
                return unit.replace('km', 'mil')
        return unit

    @property
    def icon(self):
        """Return the icon."""
        return RESOURCES[self._attribute][2]
