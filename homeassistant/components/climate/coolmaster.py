"""
CoolMasterNet platform that offers control of CoolMasteNet Climate Devices.

For more details about this platform, please refer to the documentation
https://www.home-assistant.io/components/climate.coolmaster/
"""

import logging

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA, STATE_AUTO, STATE_COOL, STATE_DRY, STATE_FAN_ONLY,
    STATE_HEAT, SUPPORT_FAN_MODE, SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_HOST, CONF_PORT, TEMP_CELSIUS, TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pycoolmasternet==0.0.4']

DOMAIN = 'coolmaster'

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE |
                 SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF)

FAN_ONLY_OVERRIDE = 'fan'

DEFAULT_PORT = 10102

AVAILABLE_MODES = [STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_DRY,
                   STATE_FAN_ONLY]

FAN_MODES = ['low', 'med', 'high', 'auto']

CONF_SUPPORTED_MODES = 'supported_modes'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SUPPORTED_MODES, default=AVAILABLE_MODES):
        vol.All(cv.ensure_list, [vol.In(AVAILABLE_MODES)]),
})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the CoolMasterNet climate platform."""
    from pycoolmasternet import CoolMasterNet

    supported_modes = config.get(CONF_SUPPORTED_MODES)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    cool = CoolMasterNet(host, port=port)

    all_devices = [CoolmasterClimate(device, supported_modes)
                   for device in cool.devices()]

    async_add_entities(all_devices, True)


class CoolmasterClimate(ClimateDevice):
    """Representation of a coolmaster climate device."""

    def __init__(self, device, supported_modes):
        """Initialize the climate device."""
        _LOGGER.debug("Creating device %s", device.uid)
        self._device = device
        self._uid = device.uid
        self._operation_list = supported_modes
        self._target_temperature = None
        self._current_temperature = None
        self._current_fan_mode = None
        self._current_operation = None
        self._on = None
        self._unit = None

    def update(self):
        """Pull state from CoolMasterNet."""
        status = self._device.status
        self._target_temperature = status['thermostat']
        self._current_temperature = status['temperature']
        self._current_fan_mode = status['fan_speed']
        self._on = status['is_on']

        device_mode = status['mode']
        if device_mode == FAN_ONLY_OVERRIDE:
            self._current_operation = STATE_FAN_ONLY
        else:
            self._current_operation = device_mode

        if status['unit'] == 'celsius':
            self._unit = TEMP_CELSIUS
        else:
            self._unit = TEMP_FAHRENHEIT

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._uid

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            'identifiers': {
                (DOMAIN, self.unique_id),
            },
            'name': self.name,
            'manufacturer': 'CoolMasterNet',
        }

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self.unique_id

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we are trying to reach."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._on

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return FAN_MODES

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            _LOGGER.debug("Setting temp of %s to %s", self.unique_id,
                          str(temp))
            self._device.set_thermostat(str(temp))
            self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Setting fan mode of %s to %s", self.unique_id,
                      fan_mode)
        self._device.set_fan_speed(fan_mode)
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        if operation_mode == STATE_FAN_ONLY:
            operation_mode = FAN_ONLY_OVERRIDE

        _LOGGER.debug("Setting operation mode of %s to %s", self.unique_id,
                      operation_mode)
        self._device.set_mode(operation_mode)
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn on."""
        _LOGGER.debug("Turning %s on", self.unique_id)
        self._device.turn_on()
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off."""
        _LOGGER.debug("Turning %s off", self.unique_id)
        self._device.turn_off()
        self.schedule_update_ha_state()
