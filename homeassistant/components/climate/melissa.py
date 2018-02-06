"""
Support for Melissa Climate A/C.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.melissa/
"""
import logging

from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_ON_OFF, STATE_AUTO, STATE_HEAT, STATE_COOL, STATE_DRY,
    STATE_FAN_ONLY, SUPPORT_FAN_MODE
)
from homeassistant.components.fan import SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH
from homeassistant.components.melissa import DATA_MELISSA
from homeassistant.const import (
    TEMP_CELSIUS, STATE_ON, STATE_OFF, STATE_IDLE, ATTR_TEMPERATURE,
    PRECISION_WHOLE
)

DEPENDENCIES = ['melissa']

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (SUPPORT_FAN_MODE | SUPPORT_OPERATION_MODE |
                 SUPPORT_ON_OFF | SUPPORT_TARGET_TEMPERATURE)

OP_MODES = [
    STATE_AUTO, STATE_COOL, STATE_DRY, STATE_FAN_ONLY, STATE_HEAT
]

FAN_MODES = [
    STATE_AUTO, SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM
]


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Iterate through and add all Melissa devices."""
    api = hass.data[DATA_MELISSA]
    devices = api.fetch_devices().values()

    all_devices = []

    for device in devices:
        all_devices.append(MelissaClimate(
            api, device['serial_number'], device))

    add_devices(all_devices)


class MelissaClimate(ClimateDevice):
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
        """Return the name of the thermostat, if any."""
        return self._name

    @property
    def is_on(self):
        """Return current state."""
        if self._cur_settings is not None:
            return self._cur_settings[self._api.STATE] in (
                self._api.STATE_ON, self._api.STATE_IDLE)
        return None

    @property
    def current_fan_mode(self):
        """Return the current fan mode."""
        if self._cur_settings is not None:
            return self.melissa_fan_to_hass(
                self._cur_settings[self._api.FAN])

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._data:
            return self._data[self._api.TEMP]

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return PRECISION_WHOLE

    @property
    def current_operation(self):
        """Return the current operation mode."""
        if self._cur_settings is not None:
            return self.melissa_op_to_hass(
                self._cur_settings[self._api.MODE])

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OP_MODES

    @property
    def fan_list(self):
        """List of available fan modes."""
        return FAN_MODES

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self._cur_settings is not None:
            return self._cur_settings[self._api.TEMP]

    @property
    def state(self):
        """Return current state."""
        if self._cur_settings is not None:
            return self.melissa_state_to_hass(
                self._cur_settings[self._api.STATE])

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum supported temperature for the thermostat."""
        return 16

    @property
    def max_temp(self):
        """Return the maximum supported temperature for the thermostat."""
        return 30

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        self.send({self._api.TEMP: temp})

    def set_fan_mode(self, fan):
        """Set fan mode."""
        fan_mode = self.hass_fan_to_melissa(fan)
        self.send({self._api.FAN: fan_mode})

    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        mode = self.hass_mode_to_melissa(operation_mode)
        self.send({self._api.MODE: mode})

    def turn_on(self):
        """Turn on device."""
        self.send({self._api.STATE: self._api.STATE_ON})

    def turn_off(self):
        """Turn off device."""
        self.send({self._api.STATE: self._api.STATE_OFF})

    def send(self, value):
        """Sending action to service."""
        try:
            old_value = self._cur_settings.copy()
            self._cur_settings.update(value)
        except AttributeError:
            old_value = None
        if not self._api.send(self._serial_number, self._cur_settings):
            self._cur_settings = old_value
            return False
        else:
            return True

    def update(self):
        """Get latest data from Melissa."""
        try:
            self._data = self._api.status(cached=True)[self._serial_number]
            self._cur_settings = self._api.cur_settings(
                self._serial_number
            )['controller']['_relation']['command_log']
        except KeyError:
            _LOGGER.warning(
                'Unable to update entity %s', self.entity_id)

    def melissa_state_to_hass(self, state):
        """Translate Melissa states to hass states."""
        if state == self._api.STATE_ON:
            return STATE_ON
        elif state == self._api.STATE_OFF:
            return STATE_OFF
        elif state == self._api.STATE_IDLE:
            return STATE_IDLE
        else:
            return None

    def melissa_op_to_hass(self, mode):
        """Translate Melissa modes to hass states."""
        if mode == self._api.MODE_AUTO:
            return STATE_AUTO
        elif mode == self._api.MODE_HEAT:
            return STATE_HEAT
        elif mode == self._api.MODE_COOL:
            return STATE_COOL
        elif mode == self._api.MODE_DRY:
            return STATE_DRY
        elif mode == self._api.MODE_FAN:
            return STATE_FAN_ONLY
        else:
            _LOGGER.warning(
                "Operation mode %s could not be mapped to hass", mode)
            return None

    def melissa_fan_to_hass(self, fan):
        """Translate Melissa fan modes to hass modes."""
        if fan == self._api.FAN_AUTO:
            return STATE_AUTO
        elif fan == self._api.FAN_LOW:
            return SPEED_LOW
        elif fan == self._api.FAN_MEDIUM:
            return SPEED_MEDIUM
        elif fan == self._api.FAN_HIGH:
            return SPEED_HIGH
        else:
            _LOGGER.warning("Fan mode %s could not be mapped to hass", fan)
            return None

    def hass_mode_to_melissa(self, mode):
        """Translate hass states to melissa modes."""
        if mode == STATE_AUTO:
            return self._api.MODE_AUTO
        elif mode == STATE_HEAT:
            return self._api.MODE_HEAT
        elif mode == STATE_COOL:
            return self._api.MODE_COOL
        elif mode == STATE_DRY:
            return self._api.MODE_DRY
        elif mode == STATE_FAN_ONLY:
            return self._api.MODE_FAN
        else:
            _LOGGER.warning("Melissa have no setting for %s mode", mode)

    def hass_fan_to_melissa(self, fan):
        """Translate hass fan modes to melissa modes."""
        if fan == STATE_AUTO:
            return self._api.FAN_AUTO
        elif fan == SPEED_LOW:
            return self._api.FAN_LOW
        elif fan == SPEED_MEDIUM:
            return self._api.FAN_MEDIUM
        elif fan == SPEED_HIGH:
            return self._api.FAN_HIGH
        else:
            _LOGGER.warning("Melissa have no setting for %s fan mode", fan)
