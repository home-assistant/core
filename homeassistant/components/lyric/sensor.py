"""
Support for Honeywell Lyric thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lyric
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from .const import DATA_LYRIC_CLIENT, DATA_LYRIC_DEVICES, DOMAIN

DEPENDENCIES = ['lyric']

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_SCAN_INTERVAL):
        vol.All(vol.Coerce(int), vol.Range(min=1))
})


async def async_setup_entry(
        hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up Lyric sensor based on a config entry."""
    lyric = hass.data[DOMAIN][DATA_LYRIC_CLIENT]

    try:
        devices = lyric.devices()
    except Exception as exception:
        raise PlatformNotReady from exception

    hass.data[DOMAIN][DATA_LYRIC_DEVICES] = devices

    devices = []
    for location, device in lyric.devices():
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
        if device.nextPeriodTime:
            devices.append(LyricSensor(
                location, device, hass, 'nextPeriodTime',
                'Next Period Time', '', 'mdi:clock'))
        if device.thermostatSetpointStatus:
            devices.append(LyricSensor(
                location, device, hass, 'thermostatSetpointStatus',
                'Status', '', 'mdi:thermostat'))

    async_add_entities(devices, True)


class LyricSensor(Entity):
    """Representation of a Lyric thermostat."""

    def __init__(self, location, device, hass, key, key_name,
                 unit_of_measurement=None, icon=None) -> None:
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
    def unique_id(self) -> str:
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
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    def update(self):
        """Get values from lyric."""
        if self.device:
            if self.key == 'thermostatSetpointStatus':
                status = getattr(self.device, self.key)
                if status == 'NoHold':
                    self._state = 'Following Schedule'
                elif status == 'HoldUntil':
                    self._state = 'Held until {}'.format(
                        self.device.nextPeriodTime[:-3])
                elif status == 'PermanentHold':
                    self._state = 'Held Permanently'
                elif status == 'VacationHold':
                    self._state = 'Holiday'
            else:
                self._state = getattr(self.device, self.key)
            self._available = True
