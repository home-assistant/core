"""
Support for VOC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.volvooncall/

"""
import logging

from homeassistant.components.volvooncall import VolvoEntity, RESOURCES, CONF_SCANDINAVIAN_MILES

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

        if val and 'mil' in self.unit_of_measurement:
            val /= 10

        if val and self._attribute == 'odometer':
            val = round(val / 1000)

        if val and self._attribute == 'average_fuel_consumption':
            val = round(val, 1)

        return val

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._state.config[CONF_SCANDINAVIAN_MILES]:
            return RESOURCES[self._attribute][3].replace('km', 'mil')
        else:
            return RESOURCES[self._attribute][3]

    @property
    def icon(self):
        """Return the icon."""
        return RESOURCES[self._attribute][2]
