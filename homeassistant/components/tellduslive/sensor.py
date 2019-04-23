"""Support for Tellstick Net/Telstick Live sensors."""
import logging

from homeassistant.components import sensor, tellduslive
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_ILLUMINANCE, DEVICE_CLASS_TEMPERATURE,
    POWER_WATT, TEMP_CELSIUS)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .entry import TelldusLiveEntity

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPE_TEMPERATURE = 'temp'
SENSOR_TYPE_HUMIDITY = 'humidity'
SENSOR_TYPE_RAINRATE = 'rrate'
SENSOR_TYPE_RAINTOTAL = 'rtot'
SENSOR_TYPE_WINDDIRECTION = 'wdir'
SENSOR_TYPE_WINDAVERAGE = 'wavg'
SENSOR_TYPE_WINDGUST = 'wgust'
SENSOR_TYPE_UV = 'uv'
SENSOR_TYPE_WATT = 'watt'
SENSOR_TYPE_LUMINANCE = 'lum'
SENSOR_TYPE_DEW_POINT = 'dewp'
SENSOR_TYPE_BAROMETRIC_PRESSURE = 'barpress'

SENSOR_TYPES = {
    SENSOR_TYPE_TEMPERATURE:
    ['Temperature', TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    SENSOR_TYPE_HUMIDITY: ['Humidity', '%', None, DEVICE_CLASS_HUMIDITY],
    SENSOR_TYPE_RAINRATE: ['Rain rate', 'mm/h', 'mdi:water', None],
    SENSOR_TYPE_RAINTOTAL: ['Rain total', 'mm', 'mdi:water', None],
    SENSOR_TYPE_WINDDIRECTION: ['Wind direction', '', '', None],
    SENSOR_TYPE_WINDAVERAGE: ['Wind average', 'm/s', '', None],
    SENSOR_TYPE_WINDGUST: ['Wind gust', 'm/s', '', None],
    SENSOR_TYPE_UV: ['UV', 'UV', '', None],
    SENSOR_TYPE_WATT: ['Power', POWER_WATT, '', None],
    SENSOR_TYPE_LUMINANCE: ['Luminance', 'lx', None, DEVICE_CLASS_ILLUMINANCE],
    SENSOR_TYPE_DEW_POINT:
    ['Dew Point', TEMP_CELSIUS, None, DEVICE_CLASS_TEMPERATURE],
    SENSOR_TYPE_BAROMETRIC_PRESSURE: ['Barometric Pressure', 'kPa', '', None],
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Old way of setting up TelldusLive.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tellduslive sensors dynamically."""
    async def async_discover_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[tellduslive.DOMAIN]
        async_add_entities([TelldusLiveSensor(client, device_id)])

    async_dispatcher_connect(
        hass,
        tellduslive.TELLDUS_DISCOVERY_NEW.format(
            sensor.DOMAIN, tellduslive.DOMAIN), async_discover_sensor)


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
        return '{} {}'.format(super().name, self.quantity_name or '').strip()

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.available:
            return None
        if self._type == SENSOR_TYPE_TEMPERATURE:
            return self._value_as_temperature
        if self._type == SENSOR_TYPE_HUMIDITY:
            return self._value_as_humidity
        if self._type == SENSOR_TYPE_LUMINANCE:
            return self._value_as_luminance
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

    @property
    def device_class(self):
        """Return the device class."""
        return SENSOR_TYPES[self._type][3] \
            if self._type in SENSOR_TYPES else None

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "{}-{}-{}".format(*self._id)
