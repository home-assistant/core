"""ZWave Thermostat."""

# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.thermostat import DOMAIN
from homeassistant.components.thermostat import (
    ThermostatDevice,
    STATE_IDLE)
from homeassistant.components import zwave
from homeassistant.const import TEMP_FAHRENHEIT, TEMP_CELSIUS

CONF_NAME = 'name'
DEFAULT_NAME = 'ZWave Thermostat'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ZWave thermostats."""
    if discovery_info is None or zwave.NETWORK is None:
        return

    node = zwave.NETWORK.nodes[discovery_info[zwave.ATTR_NODE_ID]]
    value = node.values[discovery_info[zwave.ATTR_VALUE_ID]]
    value.set_change_verified(False)
    add_devices([ZWaveThermostat(value)])


# pylint: disable=too-many-arguments
class ZWaveThermostat(zwave.ZWaveDeviceEntity, ThermostatDevice):
    """Represents a HeatControl thermostat."""

    def __init__(self, value):
        """Initialize the zwave thermostat."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        zwave.ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._node = value.node
        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = STATE_IDLE
        self._current_operation_state = STATE_IDLE
        self._unit = None
        self.update_properties()
        # register listener
        dispatcher.connect(
            self.value_changed, ZWaveNetwork.SIGNAL_VALUE_CHANGED)

    def value_changed(self, value):
        """Called when a value has changed on the network."""
        if self._value.node == value.node:
            self.update_properties()
            self.update_ha_state()

    def update_properties(self):
        """Callback on data change for the registered node/value pair."""
        # set point
        for _, value in self._node.get_values(class_id=0x43).items():
            if int(value.data) != 0:
                self._target_temperature = int(value.data)
        # Operation
        for _, value in self._node.get_values(class_id=0x40).items():
            self._current_operation = value.data_as_string
        # Current Temp
        for _, value in self._node.get_values_for_command_class(0x31).items():
            self._current_temperature = int(value.data)
            self._unit = value.units
        # COMMAND_CLASS_THERMOSTAT_OPERATING_STATE
        for _, value in self._node.get_values(class_id=0x42).items():
            self._current_operation_state = value.data_as_string

    @property
    def should_poll(self):
        """No polling on ZWave."""
        return False

    @property
    def is_fan_on(self):
        """Return if the fan is not idle."""
        return self._current_operation_state != 'Idle'

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
        return self.hass.config.temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def operation(self):
        """Return the operation mode."""
        return self._current_operation

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    def set_temperature(self, temperature):
        """Set new target temperature."""
        # set point
        for _, value in self._node.get_values_for_command_class(0x43).items():
            if int(value.data) != 0:
                value.data = temperature
