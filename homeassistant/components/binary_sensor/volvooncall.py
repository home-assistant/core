"""
Support for VOC.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.volvooncall/

"""
import logging

from homeassistant.components.volvooncall import VolvoEntity
from homeassistant.components.binary_sensor import BinarySensorDevice

_LOGGER = logging.getLogger(__name__)

SENSORS = [('washer_fluid_level', 'Washer fluid'),
           ('brake_fluid', 'Brake Fluid'),
           ('service_warning_status', 'Service'),
           ('bulb_failures', 'Bulbs'),
           ('doors', 'Doors'),
           ('windows', 'Windows')]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Volvo sensors."""
    if discovery_info is None:
        return
    add_devices(VolvoSensor(hass, discovery_info, sensor)
                for sensor in SENSORS)


class VolvoSensor(VolvoEntity, BinarySensorDevice):
    """Representation of a Volvo sensor."""

    def __init__(self, hass, vehicle, sensor):
        """Initialize the sensor."""
        super().__init__(hass, vehicle)
        self._sensor = sensor

    @property
    def _name(self):
        """Name of sensor."""
        return self._sensor[1]

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        attr = self._sensor[0]
        val = getattr(self.vehicle, attr)
        if attr == 'bulb_failures':
            return len(val) > 0
        elif attr in ['doors', 'windows']:
            return any([val[key] for key in val if 'Open' in key])
        else:
            return val != 'Normal'

    @property
    def device_class(self):
        """Return the class of this sensor, from SENSOR_CLASSES."""
        return 'safety'
