"""
Support for Vera sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.vera/
"""
import logging

import homeassistant.util.dt as dt_util
from homeassistant.const import (
    ATTR_ARMED, ATTR_BATTERY_LEVEL, ATTR_LAST_TRIP_TIME, ATTR_TRIPPED,
    TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.entity import Entity
from homeassistant.components.vera import (
    VeraDevice, VERA_DEVICES, VERA_CONTROLLER)

DEPENDENCIES = ['vera']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Perform the setup for Vera controller devices."""
    add_devices_callback(
        VeraSensor(device, VERA_CONTROLLER)
        for device in VERA_DEVICES['sensor'])


class VeraSensor(VeraDevice, Entity):
    """Representation of a Vera Sensor."""

    def __init__(self, vera_device, controller):
        """Initialize the sensor."""
        self.current_value = None
        self._temperature_units = None
        VeraDevice.__init__(self, vera_device, controller)

    @property
    def state(self):
        """Return the name of the sensor."""
        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        if self.vera_device.category == "Temperature Sensor":
            return self._temperature_units
        elif self.vera_device.category == "Light Sensor":
            return 'lux'
        elif self.vera_device.category == "Humidity Sensor":
            return '%'

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level + '%'

        if self.vera_device.is_armable:
            armed = self.vera_device.is_armed
            attr[ATTR_ARMED] = 'True' if armed else 'False'

        if self.vera_device.is_trippable:
            last_tripped = self.vera_device.last_trip
            if last_tripped is not None:
                utc_time = dt_util.utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = utc_time.isoformat()
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.is_tripped
            attr[ATTR_TRIPPED] = 'True' if tripped else 'False'

        attr['Vera Device Id'] = self.vera_device.vera_device_id
        return attr

    def update(self):
        """Update the state."""
        if self.vera_device.category == "Temperature Sensor":
            current_temp = self.vera_device.temperature
            vera_temp_units = (
                self.vera_device.vera_controller.temperature_units)

            if vera_temp_units == 'F':
                self._temperature_units = TEMP_FAHRENHEIT
            else:
                self._temperature_units = TEMP_CELSIUS

            if self.hass:
                temp = self.hass.config.temperature(
                    current_temp,
                    self._temperature_units)

                current_temp, self._temperature_units = temp

            self.current_value = current_temp
        elif self.vera_device.category == "Light Sensor":
            self.current_value = self.vera_device.light
        elif self.vera_device.category == "Humidity Sensor":
            self.current_value = self.vera_device.humidity
        elif self.vera_device.category == "Sensor":
            tripped = self.vera_device.is_tripped
            self.current_value = 'Tripped' if tripped else 'Not Tripped'
        else:
            self.current_value = 'Unknown'
