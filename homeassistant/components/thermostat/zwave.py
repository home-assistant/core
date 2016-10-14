"""ZWave Thermostat."""

# Because we do not compile openzwave on CI
# pylint: disable=import-error
import logging
from homeassistant.components.thermostat import DOMAIN
from homeassistant.components.thermostat import (
    ThermostatDevice,
    STATE_IDLE)
from homeassistant.components import zwave
from homeassistant.const import TEMP_FAHRENHEIT, TEMP_CELSIUS

_LOGGER = logging.getLogger(__name__)

CONF_NAME = 'name'
DEFAULT_NAME = 'ZWave Thermostat'

REMOTEC = 0x5254
REMOTEC_ZXT_120 = 0x8377
REMOTEC_ZXT_120_THERMOSTAT = (REMOTEC, REMOTEC_ZXT_120)

WORKAROUND_IGNORE = 'ignore'

DEVICE_MAPPINGS = {
    REMOTEC_ZXT_120_THERMOSTAT: WORKAROUND_IGNORE
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ZWave thermostats."""
    if discovery_info is None or zwave.NETWORK is None:
        _LOGGER.debug("No discovery_info=%s or no NETWORK=%s",
                      discovery_info, zwave.NETWORK)
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.const.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.const.ATTR_VALUE_ID]]
    value.set_change_verified(False)
    # Make sure that we have values for the key before converting to int
    if (value.node.manufacturer_id.strip() and
            value.node.product_id.strip()):
        specific_sensor_key = (int(value.node.manufacturer_id, 16),
                               int(value.node.product_id, 16))
        if specific_sensor_key in DEVICE_MAPPINGS:
            if DEVICE_MAPPINGS[specific_sensor_key] == WORKAROUND_IGNORE:
                _LOGGER.debug("Remotec ZXT-120 Zwave Thermostat, ignoring")
                return
    if not (value.node.get_values_for_command_class(
            zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL) and
            value.node.get_values_for_command_class(
                zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT)):
        return

    if value.command_class != zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL and \
       value.command_class != zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT:
        return

    add_devices([ZWaveThermostat(value)])
    _LOGGER.debug("discovery_info=%s and zwave.NETWORK=%s",
                  discovery_info, zwave.NETWORK)


# pylint: disable=too-many-arguments, too-many-instance-attributes
# pylint: disable=abstract-method
class ZWaveThermostat(zwave.ZWaveDeviceEntity, ThermostatDevice):
    """Represents a HeatControl thermostat."""

    def __init__(self, value):
        """Initialize the zwave thermostat."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._node = value.node
        self._index = value.index
        self._current_temperature = None
        self._unit = None
        self._current_operation_state = STATE_IDLE
        self._target_temperature = None
        self._current_fan_state = STATE_IDLE
        self.update_properties()
        # register listener
        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.value_id == value.value_id or \
           self._value.node == value.node:
            self.update_properties()
            self.update_ha_state()

    def update_properties(self):
        """Callback on data change for the registered node/value pair."""
        # current Temp
        for _, value in self._node.get_values_for_command_class(
                zwave.const.COMMAND_CLASS_SENSOR_MULTILEVEL).items():
            if value.label == 'Temperature':
                self._current_temperature = int(value.data)
                self._unit = value.units

        # operation state
        for _, value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_OPERATING_STATE)
                         .items()):
            self._current_operation_state = value.data_as_string

        # target temperature
        temps = []
        for _, value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT)
                         .items()):
            temps.append(int(value.data))
            if value.index == self._index:
                self._target_temperature = value.data
        self._target_temperature_high = max(temps)
        self._target_temperature_low = min(temps)

        # fan state
        for _, value in (self._node.get_values(
                class_id=zwave.const.COMMAND_CLASS_THERMOSTAT_FAN_STATE)
                         .items()):
            self._current_fan_state = value.data_as_string

    @property
    def should_poll(self):
        """No polling on ZWave."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        unit = self._unit
        if unit == 'C':
            return TEMP_CELSIUS
        elif unit == 'F':
            return TEMP_FAHRENHEIT
        else:
            return unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation_state

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def is_fan_on(self):
        """Return true if the fan is on."""
        return not (self._current_fan_state == 'Idle' or
                    self._current_fan_state == STATE_IDLE)

    def set_temperature(self, temperature):
        """Set new target temperature."""
        # set point
        for _, value in self._node.get_values_for_command_class(
                zwave.const.COMMAND_CLASS_THERMOSTAT_SETPOINT).items():
            if int(value.data) != 0 and value.index == self._index:
                value.data = temperature
                break
