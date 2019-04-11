"""
Support for Honeywell Lyric thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lyric
"""
import logging

import voluptuous as vol

from homeassistant.components.lyric import DATA_LYRIC
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.helpers.entity import Entity

DEPENDENCIES = ['lyric']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1))
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Lyric thermostat."""
    if discovery_info is None:
        return

    _LOGGER.debug('Set up Lyric sensor platform')

    devices = []
    for location, device in hass.data[DATA_LYRIC].thermostats():
        if device.indoorTemperature:
            devices.append(LyricSensor(
                location, device, hass, 'indoorTemperature', 'Temperature',
                hass.config.units.temperature_unit, 'mdi:thermometer'))
        if device.indoorHumidity:
            devices.append(LyricSensor(
                location, device, hass, 'indoorHumidity', 'Humidity',
                '%', 'mdi:water-percent'))
        if device.outdoorTemperature:
            devices.append(LyricSensor(
                location, device, hass, 'outdoorTemperature',
                'Temperature Outside',
                hass.config.units.temperature_unit, 'mdi:thermometer'))
        if device.displayedOutdoorHumidity:
            devices.append(LyricSensor(
                location, device, hass, 'displayedOutdoorHumidity',
                'Humidity Outside', '%', 'mdi:water-percent'))

    add_devices(devices, True)


class LyricSensor(Entity):
    """Representation of a Lyric thermostat."""

    def __init__(self, location, device, hass, key, key_name,
                 unit_of_measurement=None, icon=None):
        """Initialize the sensor."""
        self._unique_id = '{}_{}'.format(
            device.macID, key_name.replace(" ", "_"))
        self._name = '{} {}'.format(device.name, key_name)
        self._unit_of_measurement = unit_of_measurement
        self._icon = icon
        self._state = None
        self._available = False
        self.device = device
        self.key = key

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return unique ID for the sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    def update(self):
        """Get values from lyric."""
        if self.device:
            self._state = getattr(self.device, self.key)
            self._available = True
