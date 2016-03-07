"""
ZWave Thermostat.

"""

# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.thermostat import DOMAIN
from homeassistant.components.thermostat import ThermostatDevice
from homeassistant.components.zwave import (
    ATTR_NODE_ID, ATTR_VALUE_ID, NETWORK,
    ZWaveDeviceEntity)

CONF_NAME = 'name'
DEFAULT_NAME = 'ZWave Thermostat'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ZWave thermostats."""
    if discovery_info is None or NETWORK is None:
        return

    node = NETWORK.nodes[discovery_info[ATTR_NODE_ID]]
    value = node.values[discovery_info[ATTR_VALUE_ID]]
    value.set_change_verified(False)
    add_devices([ZWaveThermostat(value)])


# pylint: disable=too-many-arguments
class ZWaveThermostat(ZWaveDeviceEntity, ThermostatDevice):
    """Represents a HeatControl thermostat."""
    def __init__(self, value):
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        from homeassistant.helpers.temperature import convert
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._node = value.node
        self._target_temperature = round(convert(71, TEMP_FAHRENHEIT, self.hass.config.temperature_unit))
        self._current_temperature = 90
        self._current_operation = "Idle"
        self._current_operation_state = "Idle"
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
        """ Callback on data change for the registered node/value pair. """
        # set point
        for _, value in self._node.get_values_for_command_class(0x43).items():
            if int(value.data) != 0:
                self._target_temperature = value.data
        # Operation
        for _, value in self._node.get_values_for_command_class(0x40).items():
            self._current_operation = value.data
        # Current Temp
        for _, value in self._node.get_values_for_command_class(0x31).items():
            if int(value.data) != 0:
                self._current_temperature = value.data
        # COMMAND_CLASS_THERMOSTAT_OPERATING_STATE
        for _, value in self._node.get_values_for_command_class(0x42).items():
            self._current_operation_state = value.data

    @property
    def should_poll(self):
        """No polling on ZWave"""
        return False

    @property
    def is_fan_on(self):
        return self._current_operation_state != 'Idle'

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.hass.config.temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def operation(self):
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
