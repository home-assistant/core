"""
Support for ZWave climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.climate import DOMAIN
from homeassistant.components.climate import (
    ClimateDevice, ATTR_OPERATION_MODE)
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components import zwave
from homeassistant.const import (
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

CONF_NAME = 'name'
DEFAULT_NAME = 'ZWave Climate'

REMOTEC = 0x5254
REMOTEC_ZXT_120 = 0x8377
REMOTEC_ZXT_120_THERMOSTAT = (REMOTEC, REMOTEC_ZXT_120)

HORSTMANN = 0x0059
HORSTMANN_HRT4_ZW = 0x3
HORSTMANN_HRT4_ZW_THERMOSTAT = (HORSTMANN, HORSTMANN_HRT4_ZW)

WORKAROUND_ZXT_120 = 'zxt_120'
WORKAROUND_HRT4_ZW = 'hrt4_zw'

DEVICE_MAPPINGS = {
    REMOTEC_ZXT_120_THERMOSTAT: WORKAROUND_ZXT_120,
    HORSTMANN_HRT4_ZW_THERMOSTAT: WORKAROUND_HRT4_ZW
}

SET_TEMP_TO_INDEX = {
    'Heat': 1,
    'Cool': 2,
    'Auto': 3,
    'Aux Heat': 4,
    'Resume': 5,
    'Fan Only': 6,
    'Furnace': 7,
    'Dry Air': 8,
    'Moist Air': 9,
    'Auto Changeover': 10,
    'Heat Econ': 11,
    'Cool Econ': 12,
    'Away': 13,
    'Unknown': 14
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ZWave Climate devices."""
    if discovery_info is None or zwave.NETWORK is None:
        _LOGGER.debug("No discovery_info=%s or no NETWORK=%s",
                      discovery_info, zwave.NETWORK)
        return
    temp_unit = hass.config.units.temperature_unit
    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]
    value.set_change_verified(False)
    add_devices([ZWaveClimate(value, temp_unit)])
    _LOGGER.debug("discovery_info=%s and zwave.NETWORK=%s",
                  discovery_info, zwave.NETWORK)


# pylint: disable=abstract-method
class ZWaveClimate(ZWaveDeviceEntity, ClimateDevice):
    """Represents a ZWave Climate device."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, value, temp_unit):
        """Initialize the zwave climate device."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._node = value.node
        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = None
        self._operation_list = None
        self._current_fan_mode = None
        self._fan_list = None
        self._current_swing_mode = None
        self._swing_list = None
        self._unit = temp_unit
        self._index_operation = None
        _LOGGER.debug("temp_unit is %s", self._unit)
        self._zxt_120 = None
        self._hrt4_zw = None
        self.update_properties()
        # register listener
        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)
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
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_HRT4_ZW:
                    _LOGGER.debug("Horstmann HRT4-ZW Zwave Thermostat"
                                  " workaround")
                    self._hrt4_zw = 1

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id or \
           self._value.node == value.node:
            self.update_properties()
            self.update_ha_state()
            _LOGGER.debug("Value changed on network %s", value)

    def update_properties(self):
        """Callback on data change for the registered node/value pair."""
        # Operation Mode
        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_MODE).values():
            self._current_operation = value.data
            self._index_operation = SET_TEMP_TO_INDEX.get(
                self._current_operation)
            self._operation_list = list(value.data_items)
            _LOGGER.debug("self._operation_list=%s", self._operation_list)
            _LOGGER.debug("self._current_operation=%s",
                          self._current_operation)
        # Current Temp
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL)
                      .values()):
            if value.label == 'Temperature':
                self._current_temperature = int(value.data)
                self._unit = value.units
        # Fan Mode
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_MODE)
                      .values()):
            self._current_fan_mode = value.data
            self._fan_list = list(value.data_items)
            _LOGGER.debug("self._fan_list=%s", self._fan_list)
            _LOGGER.debug("self._current_fan_mode=%s",
                          self._current_fan_mode)
        # Swing mode
        if self._zxt_120 == 1:
            for value in (self._node.get_values(
                    class_id=zwave.const.COMMAND_CLASS_CONFIGURATION)
                          .values()):
                if value.command_class == \
                   zwave.const.COMMAND_CLASS_CONFIGURATION and \
                   value.index == 33:
                    self._current_swing_mode = value.data
                    self._swing_list = list(value.data_items)
                    _LOGGER.debug("self._swing_list=%s", self._swing_list)
                    _LOGGER.debug("self._current_swing_mode=%s",
                                  self._current_swing_mode)
        # Set point
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT)
                      .values()):
            if value.data == 0:
                _LOGGER.debug("Setpoint is 0, setting default to "
                              "current_temperature=%s",
                              self._current_temperature)
                self._target_temperature = int(self._current_temperature)
                break
            if self.current_operation is not None and \
               self.current_operation != 'Off':
                if self._index_operation != value.index:
                    continue
                if self._zxt_120:
                    break
                self._target_temperature = int(value.data)
                break
            _LOGGER.debug("Device can't set setpoint based on operation mode."
                          " Defaulting to index=1")
            self._target_temperature = int(value.data)

    @property
    def should_poll(self):
        """No polling on ZWave."""
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
    def unit_of_measurement(self):
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
        operation_mode = kwargs.get(ATTR_OPERATION_MODE)
        _LOGGER.debug("set_temperature operation_mode=%s", operation_mode)

        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT)
                      .values()):
            if operation_mode is not None:
                setpoint_mode = SET_TEMP_TO_INDEX.get(operation_mode)
                if value.index != setpoint_mode:
                    continue
                _LOGGER.debug("setpoint_mode=%s", setpoint_mode)
                value.data = temperature
                break

            if self.current_operation is not None:
                if self._hrt4_zw and self.current_operation == 'Off':
                    # HRT4-ZW can change setpoint when off.
                    value.data = int(temperature)
                if self._index_operation != value.index:
                    continue
                _LOGGER.debug("self._index_operation=%s and"
                              " self._current_operation=%s",
                              self._index_operation,
                              self._current_operation)
                if self._zxt_120:
                    _LOGGER.debug("zxt_120: Setting new setpoint for %s, "
                                  " operation=%s, temp=%s",
                                  self._index_operation,
                                  self._current_operation, temperature)
                    # ZXT-120 does not support get setpoint
                    self._target_temperature = temperature
                    # ZXT-120 responds only to whole int
                    value.data = round(temperature, 0)
                    self.update_ha_state()
                    break
                else:
                    _LOGGER.debug("Setting new setpoint for %s, "
                                  "operation=%s, temp=%s",
                                  self._index_operation,
                                  self._current_operation, temperature)
                    value.data = temperature
                    break
            else:
                _LOGGER.debug("Setting new setpoint for no known "
                              "operation mode. Index=1 and "
                              "temperature=%s", temperature)
                value.data = temperature
                break

    def set_fan_mode(self, fan):
        """Set new target fan mode."""
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_MODE).
                      values()):
            if value.command_class == \
               zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_MODE and \
               value.index == 0:
                value.data = bytes(fan, 'utf-8')
                break

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_MODE).values():
            if value.command_class == \
               zwave.const.COMMAND_CLASS_THERMOSTAT_MODE and value.index == 0:
                value.data = bytes(operation_mode, 'utf-8')
                break

    def set_swing_mode(self, swing_mode):
        """Set new target swing mode."""
        if self._zxt_120 == 1:
            for value in self._node.get_values(
                    class_id=zwave.const.COMMAND_CLASS_CONFIGURATION).values():
                if value.command_class == \
                   zwave.const.COMMAND_CLASS_CONFIGURATION and \
                   value.index == 33:
                    value.data = bytes(swing_mode, 'utf-8')
                    break
