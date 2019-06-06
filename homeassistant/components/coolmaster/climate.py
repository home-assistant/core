"""CoolMasterNet platform to control of CoolMasteNet Climate Devices."""

import logging

import voluptuous as vol

from homeassistant.components.climate import ClimateDevice, PLATFORM_SCHEMA
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_COOL, STATE_DRY, STATE_FAN_ONLY,
    STATE_HEAT, SUPPORT_FAN_MODE, SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_HOST, CONF_PORT, TEMP_CELSIUS, TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE |
                 SUPPORT_OPERATION_MODE | SUPPORT_ON_OFF)

DEFAULT_PORT = 10102

AVAILABLE_MODES = [STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_DRY,
                   STATE_FAN_ONLY]

CM_TO_HA_STATE = {
    'heat': STATE_HEAT,
    'cool': STATE_COOL,
    'auto': STATE_AUTO,
    'dry': STATE_DRY,
    'fan': STATE_FAN_ONLY,
}

HA_STATE_TO_CM = {value: key for key, value in CM_TO_HA_STATE.items()}

FAN_MODES = ['low', 'med', 'high', 'auto']

CONF_SUPPORTED_MODES = 'supported_modes'
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_SUPPORTED_MODES, default=AVAILABLE_MODES):
        vol.All(cv.ensure_list, [vol.In(AVAILABLE_MODES)]),
})

_LOGGER = logging.getLogger(__name__)


def _build_entity(device, supported_modes):
    _LOGGER.debug("Found device %s", device.uid)
    return CoolmasterClimate(device, supported_modes)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the CoolMasterNet climate platform."""
    from pycoolmasternet import CoolMasterNet

    supported_modes = config.get(CONF_SUPPORTED_MODES)
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    cool = CoolMasterNet(host, port=port)
    devices = cool.devices()

    all_devices = [_build_entity(device, supported_modes)
                   for device in devices]

    add_entities(all_devices, True)


class CoolmasterClimate(ClimateDevice):
    """Representation of a coolmaster climate device."""

    def __init__(self, device, supported_modes):
        """Initialize the climate device."""
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
        self._current_operation = CM_TO_HA_STATE[device_mode]

        if status['unit'] == 'celsius':
            self._unit = TEMP_CELSIUS
        else:
            self._unit = TEMP_FAHRENHEIT

    @property
    def unique_id(self):
        """Return unique ID for this device."""
        return self._uid

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

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

    def set_fan_mode(self, fan_mode):
        """Set new fan mode."""
        _LOGGER.debug("Setting fan mode of %s to %s", self.unique_id,
                      fan_mode)
        self._device.set_fan_speed(fan_mode)

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        _LOGGER.debug("Setting operation mode of %s to %s", self.unique_id,
                      operation_mode)
        self._device.set_mode(HA_STATE_TO_CM[operation_mode])

    def turn_on(self):
        """Turn on."""
        _LOGGER.debug("Turning %s on", self.unique_id)
        self._device.turn_on()

    def turn_off(self):
        """Turn off."""
        _LOGGER.debug("Turning %s off", self.unique_id)
        self._device.turn_off()
