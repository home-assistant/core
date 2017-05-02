"""
Support for Tellstick Net/Telstick Live.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tellduslive/
"""
import logging

from homeassistant.components.tellduslive import TelldusLiveEntity
from homeassistant.const import TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_TEMP = 'temp'
SENSOR_TYPE_HUMIDITY = 'humidity'
SENSOR_TYPE_RAINRATE = 'rrate'
SENSOR_TYPE_RAINTOTAL = 'rtot'
SENSOR_TYPE_WINDDIRECTION = 'wdir'
SENSOR_TYPE_WINDAVERAGE = 'wavg'
SENSOR_TYPE_WINDGUST = 'wgust'
SENSOR_TYPE_WATT = 'watt'
SENSOR_TYPE_LUMINANCE = 'lum'

SENSOR_TYPES = {
    SENSOR_TYPE_TEMP: ['Temperature', TEMP_CELSIUS, 'mdi:thermometer'],
    SENSOR_TYPE_HUMIDITY: ['Humidity', '%', 'mdi:water'],
    SENSOR_TYPE_RAINRATE: ['Rain rate', 'mm', 'mdi:water'],
    SENSOR_TYPE_RAINTOTAL: ['Rain total', 'mm', 'mdi:water'],
    SENSOR_TYPE_WINDDIRECTION: ['Wind direction', '', ''],
    SENSOR_TYPE_WINDAVERAGE: ['Wind average', 'm/s', ''],
    SENSOR_TYPE_WINDGUST: ['Wind gust', 'm/s', ''],
    SENSOR_TYPE_WATT: ['Watt', 'W', ''],
    SENSOR_TYPE_LUMINANCE: ['Luminance', 'lx', ''],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tellstick sensors."""
    if discovery_info is None:
        return
    add_devices(TelldusLiveSensor(hass, sensor) for sensor in discovery_info)


class TelldusLiveSensor(TelldusLiveEntity):
    """Representation of a Telldus Live sensor."""

    @property
    def device_id(self):
        """Return id of the device."""
        return self._id[0]

    @property
    def _type(self):
        """Return the type of the sensor."""
        return self._id[1]

    @property
    def _value(self):
        """Return value of the sensor."""
        return self.device.value(*self._id[1:])

    @property
    def _value_as_temperature(self):
        """Return the value as temperature."""
        return round(float(self._value), 1)

    @property
    def _value_as_luminance(self):
        """Return the value as luminance."""
        return round(float(self._value), 1)

    @property
    def _value_as_humidity(self):
        """Return the value as humidity."""
        return int(round(float(self._value)))

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(
            super().name,
            self.quantity_name or '')

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.available:
            return None
        elif self._type == SENSOR_TYPE_TEMP:
            return self._value_as_temperature
        elif self._type == SENSOR_TYPE_HUMIDITY:
            return self._value_as_humidity
        elif self._type == SENSOR_TYPE_LUMINANCE:
            return self._value_as_luminance
        else:
            return self._value

    @property
    def quantity_name(self):
        """Name of quantity."""
        return SENSOR_TYPES[self._type][0] \
            if self._type in SENSOR_TYPES else None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._type][1] \
            if self._type in SENSOR_TYPES else None

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self._type][2] \
            if self._type in SENSOR_TYPES else None
