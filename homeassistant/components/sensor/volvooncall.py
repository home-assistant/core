"""
Support for VOC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.volvooncall/

"""
import logging

from homeassistant.components.volvooncall import VolvoEntity

_LOGGER = logging.getLogger(__name__)

SENSORS = [('odometer', 'Odometer', 'km', 'mdi:speedometer'),
           ('fuel_amount', 'Fuel', 'L', 'mdi:gas-station'),
           ('fuel_amount_level', 'Fuel', '%', 'mdi:water-percent'),
           ('distance_to_empty', 'Range', 'km', 'mdi:ruler')]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Volvo sensors."""
    if discovery_info is None:
        return
    add_devices(VolvoSensor(hass, discovery_info, sensor)
                for sensor in SENSORS)


class VolvoSensor(VolvoEntity):
    """Representation of a Volvo sensor."""

    def __init__(self, hass, vehicle, sensor):
        """Initialize sensor."""
        super().__init__(hass, vehicle)
        self._sensor = sensor

    @property
    def state(self):
        """Return the state of the sensor."""
        attr = self._sensor[0]
        val = getattr(self.vehicle, attr)
        if attr == 'odometer':
            return round(val / 1000)  # km
        else:
            return val

    @property
    def _name(self):
        """Name of quantity."""
        return self._sensor[1]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._sensor[2]

    @property
    def icon(self):
        """Return the icon."""
        return self._sensor[3]
