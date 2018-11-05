"""
Support for Melissa Bobbie.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/water_heater.bobbie/
"""
import logging

from homeassistant.const import TEMP_CELSIUS

from homeassistant.components.water_heater import (
    WaterHeaterDevice, SUPPORT_AWAY_MODE)

from homeassistant.components.melissa import DATA_MELISSA

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Iterate through and add all Melissa devices."""
    api = hass.data[DATA_MELISSA]
    devices = (await api.async_fetch_devices()).values()

    all_devices = []

    for device in devices:
        if device['type'] == 'bobbie':
            all_devices.append(Bobbie(api, device['serial_number'], device))

    async_add_entities(all_devices)


class Bobbie(WaterHeaterDevice):
    """Representation of a Melissa Climate device."""

    def __init__(self, api, serial_number, init_data):
        """Initialize the climate device."""
        self._name = init_data['name']
        self._api = api
        self._serial_number = serial_number
        self._data = init_data['controller_log']
        self._state = None
        self._cur_settings = None

    @property
    def name(self):
        """Return the device name."""
        return self._name

    @property
    def available(self):
        """Return if the the device is online or not."""
        return self._data is not None

    @property
    def is_away_mode_on(self):
        """Return true if away mode is on."""
        return self._data.get('relay_state', -1) == 16

    @property
    def state(self):
        """Property for state."""
        if self._data.get('load', None):
            return 'heating'
        if self.is_away_mode_on:
            return "Away mode"
        return 'idle'

    @property
    def temperature_unit(self):
        """Property for Temperature unit."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Supported features property."""
        return SUPPORT_AWAY_MODE

    @property
    def device_state_attributes(self):
        """Device state attributes property."""
        data = dict()
        if self._data:
            data['hot'] = self._data['hot']
            data['cold'] = self._data['cold']
            data['energy'] = self._data['energy']
            data['voltage'] = self._data['voltage']
            data['current'] = self._data['current']
            data['kW'] = self._data['voltage'] * self._data['current']
        return data

    async def async_turn_away_mode_on(self):
        """Turn on away mode."""
        return await self.async_send({self._api.STATE: 'off'})

    async def async_turn_away_mode_off(self):
        """Turn off away mode."""
        return await self.async_send({self._api.STATE: 'on'})

    async def async_update(self):
        """Get latest data from Melissa."""
        try:
            self._data = (await self._api.async_status(cached=False))[
                self._serial_number]
        except KeyError:
            _LOGGER.warning(
                'Unable to update entity %s', self.entity_id)

    async def async_send(self, value):
        """Send action to service."""
        return await self._api.async_send(
            self._serial_number, 'bobbie', value)
