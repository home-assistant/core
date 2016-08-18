"""
Support for Tellstick Net/Telstick Live.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tellduslive/

"""
import logging
from datetime import datetime

from homeassistant.components import tellduslive
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, DEVICE_DEFAULT_NAME, TEMP_CELSIUS)
from homeassistant.helpers.entity import Entity

ATTR_LAST_UPDATED = "time_last_updated"

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_TEMP = "temp"
SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_RAINRATE = "rrate"
SENSOR_TYPE_RAINTOTAL = "rtot"
SENSOR_TYPE_WINDDIRECTION = "wdir"
SENSOR_TYPE_WINDAVERAGE = "wavg"
SENSOR_TYPE_WINDGUST = "wgust"
SENSOR_TYPE_WATT = "watt"
SENSOR_TYPE_LUMINANCE = "lum"

SENSOR_TYPES = {
    SENSOR_TYPE_TEMP: ['Temperature', TEMP_CELSIUS, "mdi:thermometer"],
    SENSOR_TYPE_HUMIDITY: ['Humidity', '%', "mdi:water"],
    SENSOR_TYPE_RAINRATE: ['Rain rate', 'mm', "mdi:water"],
    SENSOR_TYPE_RAINTOTAL: ['Rain total', 'mm', "mdi:water"],
    SENSOR_TYPE_WINDDIRECTION: ['Wind direction', '', ""],
    SENSOR_TYPE_WINDAVERAGE: ['Wind average', 'm/s', ""],
    SENSOR_TYPE_WINDGUST: ['Wind gust', 'm/s', ""],
    SENSOR_TYPE_WATT: ['Watt', 'W', ""],
    SENSOR_TYPE_LUMINANCE: ['Luminance', 'lx', ""],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Tellstick sensors."""
    if discovery_info is None:
        return
    add_devices(TelldusLiveSensor(sensor) for sensor in discovery_info)


class TelldusLiveSensor(Entity):
    """Representation of a Telldus Live sensor."""

    def __init__(self, sensor_id):
        """Initialize the sensor."""
        self._id = sensor_id
        self.update()
        _LOGGER.debug("created sensor %s", self)

    def update(self):
        """Update sensor values."""
        tellduslive.NETWORK.update_sensors()
        self._sensor = tellduslive.NETWORK.get_sensor(self._id)

    @property
    def _sensor_name(self):
        """Return the name of the sensor."""
        return self._sensor["name"]

    @property
    def _sensor_value(self):
        """Return the value the sensor."""
        return self._sensor["data"]["value"]

    @property
    def _sensor_type(self):
        """Return the type of the sensor."""
        return self._sensor["data"]["name"]

    @property
    def _battery_level(self):
        """Return the battery level of a sensor."""
        sensor_battery_level = self._sensor.get("battery")
        return round(sensor_battery_level * 100 / 255) \
            if sensor_battery_level else None

    @property
    def _last_updated(self):
        """Return the last update."""
        sensor_last_updated = self._sensor.get("lastUpdated")
        return str(datetime.fromtimestamp(sensor_last_updated)) \
            if sensor_last_updated else None

    @property
    def _value_as_temperature(self):
        """Return the value as temperature."""
        return round(float(self._sensor_value), 1)

    @property
    def _value_as_luminance(self):
        """Return the value as luminance."""
        return round(float(self._sensor_value), 1)

    @property
    def _value_as_humidity(self):
        """Return the value as humidity."""
        return int(round(float(self._sensor_value)))

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {}".format(self._sensor_name or DEVICE_DEFAULT_NAME,
                              self.quantity_name)

    @property
    def available(self):
        """Return true if the sensor is available."""
        return not self._sensor.get("offline", False)

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._sensor_type == SENSOR_TYPE_TEMP:
            return self._value_as_temperature
        elif self._sensor_type == SENSOR_TYPE_HUMIDITY:
            return self._value_as_humidity
        elif self._sensor_type == SENSOR_TYPE_LUMINANCE:
            return self._value_as_luminance

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        if self._battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = self._battery_level
        if self._last_updated is not None:
            attrs[ATTR_LAST_UPDATED] = self._last_updated
        return attrs

    @property
    def quantity_name(self):
        """Name of quantity."""
        return SENSOR_TYPES[self._sensor_type][0]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return SENSOR_TYPES[self._sensor_type][1]

    @property
    def icon(self):
        """Return the icon."""
        return SENSOR_TYPES[self._sensor_type][2]
