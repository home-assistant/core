"""
Support for Z-Wave climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.climate import (
    DOMAIN, ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_SWING_MODE)
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components.zwave import async_setup_platform  # noqa # pylint: disable=unused-import
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

CONF_NAME = 'name'
DEFAULT_NAME = 'Z-Wave Climate'

REMOTEC = 0x5254
REMOTEC_ZXT_120 = 0x8377
REMOTEC_ZXT_120_THERMOSTAT = (REMOTEC, REMOTEC_ZXT_120)
ATTR_OPERATING_STATE = 'operating_state'
ATTR_FAN_STATE = 'fan_state'

WORKAROUND_ZXT_120 = 'zxt_120'

DEVICE_MAPPINGS = {
    REMOTEC_ZXT_120_THERMOSTAT: WORKAROUND_ZXT_120
}


def get_device(hass, values, **kwargs):
    """Create Z-Wave entity device."""
    temp_unit = hass.config.units.temperature_unit
    return ZWaveClimate(values, temp_unit)


class ZWaveClimate(ZWaveDeviceEntity, ClimateDevice):
    """Representation of a Z-Wave Climate device."""

    def __init__(self, values, temp_unit):
        """Initialize the Z-Wave climate device."""
        ZWaveDeviceEntity.__init__(self, values, DOMAIN)
        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = None
        self._operation_list = None
        self._operating_state = None
        self._current_fan_mode = None
        self._fan_list = None
        self._fan_state = None
        self._current_swing_mode = None
        self._swing_list = None
        self._unit = temp_unit
        _LOGGER.debug("temp_unit is %s", self._unit)
        self._zxt_120 = None
        # Make sure that we have values for the key before converting to int
        if (self.node.manufacturer_id.strip() and
                self.node.product_id.strip()):
            specific_sensor_key = (
                int(self.node.manufacturer_id, 16),
                int(self.node.product_id, 16))
            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_ZXT_120:
                    _LOGGER.debug(
                        "Remotec ZXT-120 Zwave Thermostat workaround")
                    self._zxt_120 = 1
        self.update_properties()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        support = SUPPORT_TARGET_TEMPERATURE
        if self.values.fan_mode:
            support |= SUPPORT_FAN_MODE
        if self.values.mode:
            support |= SUPPORT_OPERATION_MODE
        if self._zxt_120 == 1 and self.values.zxt_120_swing_mode:
            support |= SUPPORT_SWING_MODE
        return support

    def update_properties(self):
        """Handle the data changes for node values."""
        # Operation Mode
        if self.values.mode:
            self._current_operation = self.values.mode.data
            operation_list = self.values.mode.data_items
            if operation_list:
                self._operation_list = list(operation_list)
        _LOGGER.debug("self._operation_list=%s", self._operation_list)
        _LOGGER.debug("self._current_operation=%s", self._current_operation)

        # Current Temp
        if self.values.temperature:
            self._current_temperature = self.values.temperature.data
            device_unit = self.values.temperature.units
            if device_unit is not None:
                self._unit = device_unit

        # Fan Mode
        if self.values.fan_mode:
            self._current_fan_mode = self.values.fan_mode.data
            fan_list = self.values.fan_mode.data_items
            if fan_list:
                self._fan_list = list(fan_list)
        _LOGGER.debug("self._fan_list=%s", self._fan_list)
        _LOGGER.debug("self._current_fan_mode=%s",
                      self._current_fan_mode)
        # Swing mode
        if self._zxt_120 == 1:
            if self.values.zxt_120_swing_mode:
                self._current_swing_mode = self.values.zxt_120_swing_mode.data
                swing_list = self.values.zxt_120_swing_mode.data_items
                if swing_list:
                    self._swing_list = list(swing_list)
            _LOGGER.debug("self._swing_list=%s", self._swing_list)
            _LOGGER.debug("self._current_swing_mode=%s",
                          self._current_swing_mode)
        # Set point
        if self.values.primary.data == 0:
            _LOGGER.debug("Setpoint is 0, setting default to "
                          "current_temperature=%s",
                          self._current_temperature)
            if self._current_temperature is not None:
                self._target_temperature = (
                    round((float(self._current_temperature)), 1))
        else:
            self._target_temperature = round(
                (float(self.values.primary.data)), 1)

        # Operating state
        if self.values.operating_state:
            self._operating_state = self.values.operating_state.data

        # Fan operating state
        if self.values.fan_state:
            self._fan_state = self.values.fan_state.data

    @property
    def current_fan_mode(self):
        """Return the fan speed set."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """Return a list of available fan modes."""
        return self._fan_list

    @property
    def current_swing_mode(self):
        """Return the swing mode set."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """Return a list of available swing modes."""
        return self._swing_list

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
        return self._target_temperature

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            temperature = kwargs.get(ATTR_TEMPERATURE)
        else:
            return

        self.values.primary.data = temperature

    def set_fan_mode(self, fan):
        """Set new target fan mode."""
        if self.values.fan_mode:
            self.values.fan_mode.data = fan

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        if self.values.mode:
            self.values.mode.data = operation_mode

    def set_swing_mode(self, swing_mode):
        """Set new target swing mode."""
        if self._zxt_120 == 1:
            if self.values.zxt_120_swing_mode:
                self.values.zxt_120_swing_mode.data = swing_mode

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = super().device_state_attributes
        if self._operating_state:
            data[ATTR_OPERATING_STATE] = self._operating_state
        if self._fan_state:
            data[ATTR_FAN_STATE] = self._fan_state
        return data
