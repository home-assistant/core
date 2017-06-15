"""
Support for Sensibo wifi-enabled home thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.sensibo/
"""

import asyncio
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_API_KEY, CONF_ID, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY, ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.temperature import convert as convert_temperature

REQUIREMENTS = ['pysensibo==1.0.1']

_LOGGER = logging.getLogger(__name__)

ALL = 'all'
TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_ID, default=ALL): vol.All(cv.ensure_list, [cv.string]),
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
        config[CONF_API_KEY], session=async_get_clientsession(hass),
        timeout=TIMEOUT)
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
        self._name = data['room']['name']
        self._measurements = data['measurements']
        self._ac_states = data['acState']
        self._status = data['connectionStatus']['isAlive']
        capabilities = data['remoteCapabilities']
        self._operations = sorted(capabilities['modes'].keys())
        self._current_capabilities = capabilities[
            'modes'][self.current_operation]
        temperature_unit_key = self._ac_states['temperatureUnit']
        self._temperature_unit = \
            TEMP_CELSIUS if temperature_unit_key == 'C' else TEMP_FAHRENHEIT
        self._temperatures_list = self._current_capabilities[
            'temperatures'][temperature_unit_key]['values']

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
        if self.temperature_unit == self.unit_of_measurement:
            # We are working in same units as the a/c unit. Use whole degrees
            # like the API supports.
            return 1
        else:
            # Unit conversion is going on. No point to stick to specific steps.
            return None

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
        return self._ac_states.get('fanLevel')

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._current_capabilities.get('fanLevels')

    @property
    def current_swing_mode(self):
        """Return the fan setting."""
        return self._ac_states.get('swing')

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._current_capabilities.get('swing')

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
        return self._temperatures_list[0]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._temperatures_list[-1]

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        temperature = int(temperature)
        if temperature not in self._temperatures_list:
            # Requested temperature is not supported.
            if temperature == self.target_temperature:
                return
            index = self._temperatures_list.index(self.target_temperature)
            if temperature > self.target_temperature and index < len(
                    self._temperatures_list) - 1:
                temperature = self._temperatures_list[index + 1]
            elif temperature < self.target_temperature and index > 0:
                temperature = self._temperatures_list[index - 1]
            else:
                return

        with async_timeout.timeout(TIMEOUT):
            yield from self._client.async_set_ac_state_property(
                self._id, 'targetTemperature', temperature)

    @asyncio.coroutine
    def async_set_fan_mode(self, fan):
        """Set new target fan mode."""
        with async_timeout.timeout(TIMEOUT):
            yield from self._client.async_set_ac_state_property(
                self._id, 'fanLevel', fan)

    @asyncio.coroutine
    def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        with async_timeout.timeout(TIMEOUT):
            yield from self._client.async_set_ac_state_property(
                self._id, 'mode', operation_mode)

    @asyncio.coroutine
    def async_set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        with async_timeout.timeout(TIMEOUT):
            yield from self._client.async_set_ac_state_property(
                self._id, 'swing', swing_mode)

    @asyncio.coroutine
    def async_turn_aux_heat_on(self):
        """Turn Sensibo unit on."""
        with async_timeout.timeout(TIMEOUT):
            yield from self._client.async_set_ac_state_property(
                self._id, 'on', True)

    @asyncio.coroutine
    def async_turn_aux_heat_off(self):
        """Turn Sensibo unit on."""
        with async_timeout.timeout(TIMEOUT):
            yield from self._client.async_set_ac_state_property(
                self._id, 'on', False)

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        try:
            with async_timeout.timeout(TIMEOUT):
                data = yield from self._client.async_get_device(
                    self._id, _FETCH_FIELDS)
                self._do_update(data)
        except aiohttp.client_exceptions.ClientError:
            _LOGGER.warning('Failed to connect to Sensibo servers.')
