"""
Support for Sensibo wifi-enabled home thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.sensibo/
"""

import asyncio
import logging

import aiohttp
import voluptuous as vol

from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_API_KEY, CONF_ID, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY, ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.temperature import convert as convert_temperature

REQUIREMENTS = ['pysensibo==1.0.0']

_LOGGER = logging.getLogger(__name__)

ALL = 'all'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_ID, default=ALL): vol.All(cv.ensure_list, cv.string),
})

_FETCH_FIELDS = ','.join([
    'room{name}', 'measurements', 'remoteCapabilities',
    'acState', 'connectionStatus{isAlive}'])
_INITIAL_FETCH_FIELDS = 'id,' + _FETCH_FIELDS


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up Sensibo devices."""
    import pysensibo

    client = pysensibo.SensiboClient(
        config[CONF_API_KEY], session=async_get_clientsession(hass))
    devices = []
    try:
        for dev in (
                yield from client.async_get_devices(_INITIAL_FETCH_FIELDS)):
            if config[CONF_ID] == ALL or dev['id'] in config[CONF_ID]:
                devices.append(SensiboClimate(client, dev))
    except aiohttp.client_exceptions.ClientConnectorError:
        _LOGGER.exception('Failed to connct to Sensibo servers.')
        return False

    if devices:
        async_add_devices(devices)


class SensiboClimate(ClimateDevice):
    """Representation os a Sensibo device."""

    def __init__(self, client, data):
        """Build SensiboClimate.

        client: aiohttp session.
        data: initially-fetched data.
        """
        self._client = client
        self._id = data['id']
        self._do_update(data)

    def _do_update(self, data):
        print(data)
        self._name = data['room']['name']
        self._measurements = data['measurements']
        self._capabilities = data['remoteCapabilities']
        self._ac_states = data['acState']
        self._status = data['connectionStatus']['isAlive']
        self._operations = sorted(self._capabilities['modes'].keys())
        self._current_capabilities = self._capabilities[
            'modes'][self.current_operation]
        self._temperature_unit = TEMP_CELSIUS if self._ac_states[
            'temperatureUnit'] == 'C' else TEMP_FAHRENHEIT

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_CURRENT_HUMIDITY: self.current_humidity}

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return self._temperature_unit

    @property
    def available(self):
        """Return True if entity is available."""
        return self._status

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._ac_states['targetTemperature']

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._ac_states['mode']

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._measurements['humidity']

    @property
    def current_temperature(self):
        """Return the current temperature."""
        # This field is not affected by temperature_unit.
        # It is always in C / nativeTemperatureUnit
        if 'nativeTemperatureUnit' not in self._ac_states:
            return self._measurements['temperature']
        return convert_temperature(
            self._measurements['temperature'],
            TEMP_CELSIUS,
            self.temperature_unit)

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operations

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._ac_states['fanLevel']

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._current_capabilities['fanLevels']

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        return self._ac_states['swing']

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._current_capabilities['swing']

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def is_aux_heat_on(self):
        """Return true if AC is on."""
        return self._ac_states['on']

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._current_capabilities['temperatures'][
            'C' if self.unit_of_measurement == TEMP_CELSIUS else 'F'][
                'values'][0]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._current_capabilities['temperatures'][
            'C' if self.unit_of_measurement == TEMP_CELSIUS else 'F'][
                'values'][-1]

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        yield from self._client.async_set_ac_state_property(
            self._id, 'targetTemperature', int(temperature))
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_set_fan_mode(self, fan):
        """Set new target fan mode."""
        yield from self._client.async_set_ac_state_property(
            self._id, 'fanLevel', fan)
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        yield from self._client.async_set_ac_state_property(
            self._id, 'mode', operation_mode)
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        yield from self._client.async_set_ac_state_property(
            self._id, 'swing', swing_mode)
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_turn_aux_heat_on(self):
        """Turn Sensibo unit on."""
        yield from self._client.async_set_ac_state_property(
            self._id, 'on', True)
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_turn_aux_heat_off(self):
        """Turn Sensibo unit on."""
        yield from self._client.async_set_ac_state_property(
            self._id, 'on', False)
        yield from self.async_update_ha_state()

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        try:
            data = yield from self._client.async_get_device(
                self._id, _FETCH_FIELDS)
            self._do_update(data)
        except aiohttp.client_exceptions.ClientConnectorError:
            _LOGGER.warning('Failed to connect to Sensibo servers.')
