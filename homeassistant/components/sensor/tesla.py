"""
Sensors for the Tesla sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tesla/
"""
import logging
from datetime import timedelta

from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.tesla import DOMAIN as TESLA_DOMAIN, TeslaDevice
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['tesla']

SCAN_INTERVAL = timedelta(minutes=5)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tesla sensor platform."""
    controller = hass.data[TESLA_DOMAIN]['devices']['controller']
    devices = []

    for device in hass.data[TESLA_DOMAIN]['devices']['sensor']:
        if device.bin_type == 0x4:
            devices.append(TeslaSensor(device, controller, 'inside'))
            devices.append(TeslaSensor(device, controller, 'outside'))
        else:
            devices.append(TeslaSensor(device, controller))
    add_devices(devices, True)


class TeslaSensor(TeslaDevice, Entity):
    """Representation of Tesla sensors."""

    def __init__(self, tesla_device, controller, sensor_type=None):
        """Initialisation of the sensor."""
        self.current_value = None
        self._temperature_units = None
        self.last_changed_time = None
        self.type = sensor_type
        super().__init__(tesla_device, controller)

        if self.type:
            self._name = '{} ({})'.format(self.tesla_device.name, self.type)
            self.entity_id = ENTITY_ID_FORMAT.format(
                '{}_{}'.format(self.tesla_id, self.type))
        else:
            self.entity_id = ENTITY_ID_FORMAT.format(self.tesla_id)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self._temperature_units

    def update(self):
        """Update the state from the sensor."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        self.tesla_device.update()
        if self.tesla_device.bin_type == 0x4:
            if self.type == 'outside':
                self.current_value = self.tesla_device.get_outside_temp()
            else:
                self.current_value = self.tesla_device.get_inside_temp()

            tesla_temp_units = self.tesla_device.measurement

            if tesla_temp_units == 'F':
                self._temperature_units = TEMP_FAHRENHEIT
            else:
                self._temperature_units = TEMP_CELSIUS
        else:
            self.current_value = self.tesla_device.battery_level()
