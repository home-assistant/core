"""
Support for ZWave HVAC devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hvac.zwave/
"""
# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.hvac import DOMAIN
from homeassistant.components.hvac import HvacDevice
from homeassistant.components.zwave import ZWaveDeviceEntity
from homeassistant.components import zwave
from homeassistant.const import (TEMP_FAHRENHEIT, TEMP_CELSIUS)

_LOGGER = logging.getLogger(__name__)

CONF_NAME = 'name'
DEFAULT_NAME = 'ZWave Hvac'

REMOTEC = 0x5254
REMOTEC_ZXT_120 = 0x8377
REMOTEC_ZXT_120_THERMOSTAT = (REMOTEC, REMOTEC_ZXT_120, 0)

WORKAROUND_ZXT_120 = 'zxt_120'

DEVICE_MAPPINGS = {
    REMOTEC_ZXT_120_THERMOSTAT: WORKAROUND_ZXT_120
}

ZXT_120_SET_TEMP = {
    'Heat': 1,
    'Cool': 2,
    'Dry Air': 8,
    'Auto Changeover': 10
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ZWave Hvac devices."""
    if discovery_info is None or zwave.NETWORK is None:
        _LOGGER.debug("No discovery_info=%s or no NETWORK=%s",
                      discovery_info, zwave.NETWORK)
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]
    value.set_change_verified(False)
    add_devices([ZWaveHvac(value)])
    _LOGGER.debug("discovery_info=%s and zwave.NETWORK=%s",
                  discovery_info, zwave.NETWORK)


# pylint: disable=too-many-arguments, abstract-method
class ZWaveHvac(ZWaveDeviceEntity, HvacDevice):
    """Represents a HeatControl hvac."""

    # pylint: disable=too-many-public-methods, too-many-instance-attributes
    def __init__(self, value):
        """Initialize the zwave hvac."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._node = value.node
        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = None
        self._operation_list = None
        self._current_operation_state = None
        self._current_fan_mode = None
        self._fan_list = None
        self._current_swing_mode = None
        self._swing_list = None
        self._unit = None
        self._zxt_120 = None
        self.update_properties()
        # register listener
        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)
        # Make sure that we have values for the key before converting to int
        if (value.node.manufacturer_id.strip() and
                value.node.product_id.strip()):
            specific_sensor_key = (int(value.node.manufacturer_id, 16),
                                   int(value.node.product_id, 16),
                                   value.index)

            if specific_sensor_key in DEVICE_MAPPINGS:
                if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_ZXT_120:
                    _LOGGER.debug("Remotec ZXT-120 Zwave Thermostat as HVAC")
                    self._zxt_120 = 1

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id or \
           self._value.node == value.node:
            self.update_properties()
            self.update_ha_state()
            _LOGGER.debug("Value changed on network %s", value)

    def update_properties(self):
        """Callback on data change for the registered node/value pair."""
        # Set point
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT)
                      .values()):
            if int(value.data) != 0:
                self._target_temperature = int(value.data)
        # Operation Mode
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_MODE)
                      .values()):
            self._current_operation = value.data
            self._operation_list = list(value.data_items)
            _LOGGER.debug("self._operation_list=%s", self._operation_list)
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
            self._current_operation_state = value.data
            self._fan_list = list(value.data_items)
            _LOGGER.debug("self._fan_list=%s", self._fan_list)
            _LOGGER.debug("self._current_operation_state=%s",
                          self._current_operation_state)
        # Swing mode
        if self._zxt_120 == 1:
            for value in (self._node.get_values(
                    class_id=zwave.const.COMMAND_CLASS_CONFIGURATION)
                          .values()):
                if value.command_class == 112 and value.index == 33:
                    self._current_swing_mode = value.data
                    self._swing_list = list(value.data_items)
                    _LOGGER.debug("self._swing_list=%s", self._swing_list)

    @property
    def should_poll(self):
        """No polling on ZWave."""
        return False

    @property
    def current_fan_mode(self):
        """Return the fan speed set."""
        return self._current_operation_state

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
        unit = self._unit
        if unit == 'C':
            return TEMP_CELSIUS
        elif unit == 'F':
            return TEMP_FAHRENHEIT
        else:
            _LOGGER.exception("unit_of_measurement=%s is not valid",
                              unit)

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

    def set_temperature(self, temperature):
        """Set new target temperature."""
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT)
                      .values()):
            if value.command_class != 67:
                continue
            if self._zxt_120:
                # ZXT-120 does not support get setpoint
                self._target_temperature = temperature
                if ZXT_120_SET_TEMP.get(self._current_operation) \
                   != value.index:
                    continue
                # ZXT-120 responds only to whole int
                value.data = int(round(temperature, 0))
            else:
                value.data = int(temperature)
            break

    def set_fan_mode(self, fan):
        """Set new target fan mode."""
        for value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_MODE)
                      .values()):
            if value.command_class == 68 and value.index == 0:
                value.data = bytes(fan, 'utf-8')
                break

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        for value in self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_MODE).values():
            if value.command_class == 64 and value.index == 0:
                value.data = bytes(operation_mode, 'utf-8')
                break

    def set_swing_mode(self, swing_mode):
        """Set new target swing mode."""
        if self._zxt_120 == 1:
            for value in self._node.get_values(
                    class_id=zwave.const.COMMAND_CLASS_CONFIGURATION).values():
                if value.command_class == 112 and value.index == 33:
                    value.data = bytes(swing_mode, 'utf-8')
                    break
