"""
Sensors for the Tesla sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tesla/
"""
from datetime import timedelta
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.components.tesla import DOMAIN as TESLA_DOMAIN
from homeassistant.components.tesla import TeslaDevice
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, LENGTH_KILOMETERS, LENGTH_MILES)
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
        """Initialize of the sensor."""
        self.current_value = None
        self._unit = None
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
        return self._unit

    def update(self):
        """Update the state from the sensor."""
        _LOGGER.debug("Updating sensor: %s", self._name)
        self.tesla_device.update()
        units = self.tesla_device.measurement

        if self.tesla_device.bin_type == 0x4:
            if self.type == 'outside':
                self.current_value = self.tesla_device.get_outside_temp()
            else:
                self.current_value = self.tesla_device.get_inside_temp()
            if units == 'F':
                self._unit = TEMP_FAHRENHEIT
            else:
                self._unit = TEMP_CELSIUS
        elif (self.tesla_device.bin_type == 0xA or
              self.tesla_device.bin_type == 0xB):
            self.current_value = self.tesla_device.get_value()
            tesla_dist_unit = self.tesla_device.measurement
            if tesla_dist_unit == 'LENGTH_MILES':
                self._unit = LENGTH_MILES
            else:
                self._unit = LENGTH_KILOMETERS
                self.current_value /= 0.621371
                self.current_value = round(self.current_value, 2)
        else:
            self.current_value = self.tesla_device.get_value()
            if self.tesla_device.bin_type == 0x5:
                self._unit = units
            elif self.tesla_device.bin_type in (0xA, 0xB):
                if units == 'LENGTH_MILES':
                    self._unit = LENGTH_MILES
                else:
                    self._unit = LENGTH_KILOMETERS
                    self.current_value /= 0.621371
                    self.current_value = round(self.current_value, 2)
