"""
Climate on Zigbee Home Automation networks.

For more details on this platform, please refer to the documentation
at https://home-assistant.io/components/climate.zha/
"""

import asyncio
import logging
import time

from homeassistant.components import zha
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate import (
    DOMAIN, STATE_ECO, ATTR_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE)
from homeassistant.const import (
    STATE_OFF, TEMP_CELSIUS, ATTR_TEMPERATURE)


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['zha']
ATTR_HEATING_POWER = 'heating_power'
STATE_COMFORT = 'comfort'
CLEAN_TIME_ZONE = 1
OPERATIONS = {0: STATE_OFF,
              4: STATE_COMFORT,
              5: STATE_ECO}
REVERSE_OPERATIONS = dict((v, k) for k, v in OPERATIONS.items())
OPERATION_LIST = list(OPERATIONS.values())
OFF_CODE = 0x00
COMFORT_CODE = 0x04
ECO_CODE = 0x05
NO_ERROR_ANSWER_CODE = 0x00

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

@asyncio.coroutine
def safe_read(cluster, attributes, raw=False):
    """Swallow all exceptions from network read.

    If we throw during initialization, setup fails. Rather have an
    entity that exists, but is in a maybe wrong state, than no entity.

    .. note:: Could be move to homeassistant/components/zha/__init__.py
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


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Zigbee Home Automation climate."""
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
            discovery_info[data] = discovery_info[data]\
                .split(b'\x00')[0].decode('utf-8')
        elif isinstance(discovery_info.get(data), str):
            discovery_info[data] = discovery_info[data].split('\x00')[0]

    if discovery_info['manufacturer'] == 'Stelpro' and \
            discovery_info['model'] == 'ST218':
        async_add_devices([ClimateST218(**discovery_info)],
                          update_before_add=True)
    else:
        _LOGGER.warning("ZigBee Climate %s %s not supported yet",
                        discovery_info['manufacturer'],
                        discovery_info['model'])


class ClimateST218(zha.Entity, ClimateDevice):
    """Climage Stelpro ST218."""

    _domain = DOMAIN

    def __init__(self, **kwargs):
        """Initialize the ZHA Climate."""
        super().__init__(**kwargs)

        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = None
        self._heating_power = None
        self.last_request = time.time()

        # Add Stelpro Specific
        import bellows.types as t
        # Remove the following lines when this is merged
        # https://github.com/rcloran/bellows/pull/71

        class enum8(t.uint8_t):  # pylint: disable=C0103
            """Missing bellows enum8 type."""

            _enum = True

        t.enum8 = enum8
        from bellows.zigbee.zcl import foundation
        foundation.DATA_TYPES[0x30] = ('Enumeration', t.enum8,
                                       foundation.Discrete)
        foundation.DATA_TYPE_IDX[t.enum8] = 0x30
        self._endpoint.thermostat.attributes[0x001C] = \
            ('system_mode', t.enum8)
        # END

        # pylint: disable=W0212
        self._endpoint.thermostat._attridx['setpoint_mode_manuf_specific'] = \
            0x401C
        # pylint: enable=W0212
        self._endpoint.thermostat.attributes[0x401C] = \
            ('setpoint_mode_manuf_specific', t.enum8)

    @asyncio.coroutine
    def _wait_for_clean_communication(self):
        """Ensure that we not request the device more than time by second."""
        if time.time() - self.last_request < CLEAN_TIME_ZONE:
            yield from asyncio.sleep(CLEAN_TIME_ZONE)
        self.last_request = time.time()

    @asyncio.coroutine
    def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("%s async_update", self.entity_id)
        yield from self._wait_for_clean_communication()
        result = yield from safe_read(self._endpoint.thermostat,
                                      ['local_temp',
                                       'pi_heating_demand',
                                       'occupied_heating_setpoint',
                                       'setpoint_mode_manuf_specific'])
        self.last_request = time.time()
        if not result:
            _LOGGER.warning("No result received")
            return

        try:
            self._heating_power = int(result['pi_heating_demand'])
        except (TypeError, KeyError):
            _LOGGER.warning("Can not get heating power value")
            self._heating_power = None

        raw_mode = result.get('setpoint_mode_manuf_specific')
        if raw_mode not in OPERATIONS:
            _LOGGER.warning("Mode %s not found in known modes %s",
                            raw_mode, OPERATIONS)
        self._current_operation = OPERATIONS[raw_mode]

        raw_temp = result.get('occupied_heating_setpoint')
        if raw_temp:
            self._target_temperature = raw_temp / 100.0
        raw_temp = result.get('local_temp')
        if raw_temp:
            self._current_temperature = raw_temp / 100.0

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

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
        return OPERATION_LIST

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._target_temperature is None or self._target_temperature < 0:
            return None
        return self._target_temperature

    @asyncio.coroutine
    def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        operation_mode = kwargs.get(ATTR_OPERATION_MODE)
        if operation_mode is not None:
            yield from self.async_set_operation_mode(operation_mode)

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        yield from self._wait_for_clean_communication()

        temperature = temperature * 100
        data = {'occupied_heating_setpoint': temperature}
        res = yield from self._endpoint.thermostat.write_attributes(data)
        self.last_request = time.time()
        # Check result
        for result in res:
            for subresult in result:
                if subresult.status != NO_ERROR_ANSWER_CODE:
                    _LOGGER.error("Error setting operation mode: %s",
                                  subresult.status)

    @asyncio.coroutine
    def async_set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        yield from self._wait_for_clean_communication()
        if operation_mode in (STATE_COMFORT, STATE_ECO):
            data = {'system_mode': COMFORT_CODE}
            res = yield from self._endpoint.thermostat.write_attributes(data)
        elif operation_mode == STATE_OFF:
            data = {'system_mode': OFF_CODE}
            res = yield from self._endpoint.thermostat.write_attributes(data)
        # To set eco mode we need to set comfort mode just before
        if operation_mode == STATE_ECO:
            self._wait_for_clean_communication()
            data = {'setpoint_mode_manuf_specific': ECO_CODE}
            res = yield from self._endpoint.thermostat.write_attributes(data)
        self.last_request = time.time()
        # Check result
        for result in res:
            for subresult in result:
                if subresult.status != NO_ERROR_ANSWER_CODE:
                    _LOGGER.error("Error setting operation mode: %s",
                                  subresult.status)

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = super().device_state_attributes
        if self._heating_power:
            data[ATTR_HEATING_POWER] = self._heating_power
        return data
