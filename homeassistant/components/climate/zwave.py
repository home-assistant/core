"""
Support for Z-Wave climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.climate import DOMAIN
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components import zwave
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


def get_device(hass, value, **kwargs):
    """Create zwave entity device."""
    temp_unit = hass.config.units.temperature_unit
    return ZWaveClimate(value, temp_unit)


class ZWaveClimate(ZWaveDeviceEntity, ClimateDevice):
    """Representation of a Z-Wave Climate device."""

    def __init__(self, value, temp_unit):
        """Initialize the Z-Wave climate device."""
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._index = value.index
        self._node = value.node
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
        if (value.node.manufacturer_id.strip() and
                value.node.product_id.strip()):
            specific_sensor_key = (int(value.node.manufacturer_id, 16),
                                   int(value.node.product_id, 16))
            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_ZXT_120:
                    _LOGGER.debug("Remotec ZXT-120 Zwave Thermostat"
                                  " workaround")
                    self._zxt_120 = 1
        self.update_properties()

    def update_properties(self):
        """Callback on data changes for node values."""
        # Operation Mode
        self._current_operation = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_MODE, member='data')
        operation_list = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_MODE,
            member='data_items')
        if operation_list:
            self._operation_list = list(operation_list)
        _LOGGER.debug("self._operation_list=%s", self._operation_list)
        _LOGGER.debug("self._current_operation=%s", self._current_operation)

        # Current Temp
        self._current_temperature = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL,
            label=['Temperature'], member='data')
        device_unit = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL,
            label=['Temperature'], member='units')
        if device_unit is not None:
            self._unit = device_unit

        # Fan Mode
        self._current_fan_mode = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_MODE,
            member='data')
        fan_list = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_MODE,
            member='data_items')
        if fan_list:
            self._fan_list = list(fan_list)
        _LOGGER.debug("self._fan_list=%s", self._fan_list)
        _LOGGER.debug("self._current_fan_mode=%s",
                      self._current_fan_mode)
        # Swing mode
        if self._zxt_120 == 1:
            self._current_swing_mode = (
                self.get_value(
                    class_id=zwave.const.COMMAND_CLASS_CONFIGURATION,
                    index=33,
                    member='data'))
            swing_list = self.get_value(class_id=zwave.const
                                        .COMMAND_CLASS_CONFIGURATION,
                                        index=33,
                                        member='data_items')
            if swing_list:
                self._swing_list = list(swing_list)
            _LOGGER.debug("self._swing_list=%s", self._swing_list)
            _LOGGER.debug("self._current_swing_mode=%s",
                          self._current_swing_mode)
        # Set point
        temps = []
        for value in (
                self._node.get_values(
                    class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT)
                .values()):
            temps.append((round(float(value.data)), 1))
            if value.index == self._index:
                if value.data == 0:
                    _LOGGER.debug("Setpoint is 0, setting default to "
                                  "current_temperature=%s",
                                  self._current_temperature)
                    self._target_temperature = (
                        round((float(self._current_temperature)), 1))
                    break
                else:
                    self._target_temperature = round((float(value.data)), 1)

        # Operating state
        self._operating_state = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_OPERATING_STATE,
            member='data')

        # Fan operating state
        self._fan_state = self.get_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_STATE,
            member='data')

    @property
    def should_poll(self):
        """No polling on Z-Wave."""
        return False

    @property
    def current_fan_mode(self):
        """Return the fan speed set."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    @property
    def current_swing_mode(self):
        """Return the swing mode set."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._unit == 'C':
            return TEMP_CELSIUS
        elif self._unit == 'F':
            return TEMP_FAHRENHEIT
        else:
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
        """List of available operation modes."""
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

        self.set_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT,
            index=self._index, data=temperature)
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan):
        """Set new target fan mode."""
        self.set_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_MODE,
            index=0, data=bytes(fan, 'utf-8'))

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        self.set_value(
            class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_MODE,
            index=0, data=bytes(operation_mode, 'utf-8'))

    def set_swing_mode(self, swing_mode):
        """Set new target swing mode."""
        if self._zxt_120 == 1:
            self.set_value(
                class_id=zwave.const.COMMAND_CLASS_CONFIGURATION,
                index=33, data=bytes(swing_mode, 'utf-8'))

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = super().device_state_attributes
        if self._operating_state:
            data[ATTR_OPERATING_STATE] = self._operating_state,
        if self._fan_state:
            data[ATTR_FAN_STATE] = self._fan_state
        return data

    @property
    def dependent_value_ids(self):
        """List of value IDs a device depends on."""
        return None
