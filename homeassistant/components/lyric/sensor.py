"""
Support for Honeywell Lyric thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/lyric
"""
import logging
from datetime import datetime, timedelta
import voluptuous as vol

from homeassistant.components.lyric import LyricDeviceEntity
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_SCAN_INTERVAL, DEVICE_CLASS_HUMIDITY,
                                 DEVICE_CLASS_TEMPERATURE,
                                 DEVICE_CLASS_TIMESTAMP)
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.typing import HomeAssistantType
from .const import DATA_LYRIC_CLIENT, DATA_LYRIC_DEVICES, DOMAIN

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
                device, location, hass, 'indoorTemperature', 'Temperature',
                hass.config.units.temperature_unit, 'mdi:thermometer',
                DEVICE_CLASS_TEMPERATURE))
        if device.indoorHumidity:
            devices.append(LyricSensor(
                device, location, hass, 'indoorHumidity', 'Humidity',
                '%', 'mdi:water-percent', DEVICE_CLASS_HUMIDITY))
        if device.outdoorTemperature:
            devices.append(LyricSensor(
                device, location, hass, 'outdoorTemperature',
                'Temperature Outside',
                hass.config.units.temperature_unit, 'mdi:thermometer',
                DEVICE_CLASS_TEMPERATURE))
        if device.displayedOutdoorHumidity:
            devices.append(LyricSensor(
                device, location, hass, 'displayedOutdoorHumidity',
                'Humidity Outside', '%', 'mdi:water-percent',
                DEVICE_CLASS_HUMIDITY))
        if device.nextPeriodTime:
            devices.append(LyricSensor(
                device, location, hass, 'nextPeriodTime',
                'Next Period Time', '', 'mdi:clock',
                DEVICE_CLASS_TIMESTAMP))
        if device.thermostatSetpointStatus:
            devices.append(LyricSensor(
                device, location, hass, 'thermostatSetpointStatus',
                'Status', '', 'mdi:thermostat', None))

    async_add_entities(devices, True)


class LyricSensor(LyricDeviceEntity):
    """Representation of a Lyric thermostat."""

    def __init__(self, device, location, hass, key, key_name,
                 unit_of_measurement=None, icon=None,
                 device_class=None) -> None:
        """Initialize the sensor."""
        unique_id = '{}_{}'.format(
            device.macID, key_name.replace(" ", "_"))
        self._unit_of_measurement = unit_of_measurement
        self._state = None
        self._available = False
        self.key = key

        name = '{} {}'.format(device.name, key_name)

        super().__init__(device, location, unique_id, name, icon, device_class)

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    async def _lyric_update(self) -> None:
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
                state = getattr(self.device, self.key)
                if self._device_class == DEVICE_CLASS_TIMESTAMP:
                    date = datetime.now()
                    time = datetime.strptime(state, '%H:%M:%S').replace(
                        day=date.day, month=date.month, year=date.year)
                    if time <= datetime.now():
                        date = date + timedelta(days=1)
                        time = time.replace(day=date.day)
                    state = time
                self._state = state
            self._available = True
