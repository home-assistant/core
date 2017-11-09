"""
Climate on Zigbee Home Automation networks.
For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/climate.zha/
"""

import asyncio
import logging

from homeassistant.components import zha
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate import DOMAIN
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']
ATTR_HEATING_POWER = 'heating_power'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Zigbee Home Automation lights."""
    discovery_info = zha.get_discovery_info(hass, discovery_info)
    if discovery_info is None:
        return

    endpoint = discovery_info['endpoint']

    try:
        discovery_info['local_temp'] \
            = yield from endpoint.thermostat['local_temp']
    except (AttributeError, KeyError):
        pass

    # Clean data
    for data in ('manufacturer', 'model'):
        if isinstance(discovery_info.get(data), bytes):
            discovery_info[data] = discovery_info.get(data)\
                .split(b'\x00')[0].decode('utf-8')
        if isinstance(discovery_info.get(data), str):
            discovery_info[data] = discovery_info.get(data).split('\x00')[0]

    if discovery_info['manufacturer'] == 'Stelpro' and \
            discovery_info['model'] == 'ST218':
        async_add_devices([ClimateST218(**discovery_info)],
                          update_before_add=True)
    else:
        _LOGGER.warning("ZigBee Climate %s %s not supported yet",
                        discovery_info['manufacturer'],
                        discovery_info['model'])


class ClimateST218(zha.Entity, ClimateDevice):
    """Climage Stelpro ST218"""
    _domain = DOMAIN

    def __init__(self, **kwargs):
        """Initialize the ZHA Climate."""
        super().__init__(**kwargs)

        self._modes = {0: 'off',
                       4: 'confort',
                       5: 'eco',
                       }
        self._reverse_modes = dict((v, k) for k, v in self._modes.items())

        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = None
        self._heating_power = None
        self._operation_list = list(self._modes.values())
        self._unit = 'C'

        # Add Stelpro Specific
        import bellows.types as t
        # pylint: disable=W0212
        self._endpoint.thermostat._attridx['setpoint_mode_manuf_specific'] = \
            0x401C
        # pylint: enable=W0212
        self._endpoint.thermostat.attributes[0x401C] = \
            ('setpoint_mode_manuf_specific', t.int8s)
        self._endpoint.thermostat.attributes[0x001C] = \
            ('system_mode', t.uint8_t)

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""

        @asyncio.coroutine
        def safe_read(cluster, attributes, raw=False):
            """Swallow all exceptions from network read.
            If we throw during initialization, setup fails. Rather have an
            entity that exists, but is in a maybe wrong state, than no entity.
            """
            try:
                result, _ = yield from cluster.read_attributes(
                    attributes,
                    allow_cache=False,
                    raw=raw,
                )
                return result
            except Exception:  # pylint: disable=broad-except
                return {}

        _LOGGER.debug("%s async_update", self.entity_id)

        result = yield from safe_read(self._endpoint.thermostat,
                                      ['local_temp',
                                       'pi_heating_demand',
                                       'occupied_heating_setpoint',
                                       'setpoint_mode_manuf_specific'])
        self._heating_power = int(result.get('pi_heating_demand'))
        raw_mode = result.get('setpoint_mode_manuf_specific', {})
        self._current_operation = self._modes.get(raw_mode)

        raw_temp = result.get('occupied_heating_setpoint')
        if raw_temp:
            self._target_temperature = raw_temp / 100.0
        raw_temp = result.get('local_temp')
        if raw_temp:
            self._current_temperature = raw_temp / 100.0

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._unit == 'C':
            return TEMP_CELSIUS
        elif self._unit == 'F':
            return TEMP_FAHRENHEIT
        return self._unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def current_operation(self):
        """Return the current operation mode."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return a list of available operation modes."""
        return self._operation_list

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._target_temperature < 0:
            return None
        return self._target_temperature

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            temperature = kwargs.get(ATTR_TEMPERATURE)
        else:
            return

        @asyncio.coroutine
        def safe_write(cluster, attributes):
            """Swallow all exceptions from network read.
            If we throw during initialization, setup fails. Rather have an
            entity that exists, but is in a maybe wrong state, than no entity.
            """
            try:
                results, _ = yield from cluster.write_attributes(attributes)
                return results
            except Exception:  # pylint: disable=broad-except
                return []

        temperature = temperature * 100
        data = {'occupied_heating_setpoint': temperature}
        results = yield from safe_write(self._endpoint.thermostat, data)
        # Check result
        for result in results:
            for subresult in result:
                if subresult.status != 0x00:
                    _LOGGER.error("Error setting operation mode: %s",
                                  subresult.status)

    @asyncio.coroutine
    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        if operation_mode in ('confort', 'eco'):
            data = {'system_mode': 0x04}
            res = yield from self._endpoint.thermostat.write_attributes(data)
        elif operation_mode == 'off':
            data = {'system_mode': 0x00}
            res = yield from self._endpoint.thermostat.write_attributes(data)
        if operation_mode == 'eco':
            data = {'setpoint_mode_manuf_specific': 0x05}
            res = yield from self._endpoint.thermostat.write_attributes(data)
        # Check result
        for result in res:
            for subresult in result:
                if subresult.status != 0x00:
                    _LOGGER.error("Error setting operation mode: %s",
                                  subresult.status)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = super().device_state_attributes
        if self._heating_power:
            data[ATTR_HEATING_POWER] = self._heating_power
        return data
