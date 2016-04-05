"""ZWave Thermostat."""

# Because we do not compile openzwave on CI
# pylint: disable=import-error
from homeassistant.components.thermostat import DOMAIN
from homeassistant.components.thermostat import (
    ThermostatDevice,
    STATE_IDLE)
from homeassistant.components.zwave import (
    ATTR_NODE_ID, ATTR_VALUE_ID, NETWORK,
    ZWaveDeviceEntity)
from homeassistant.const import (TEMP_FAHRENHEIT, TEMP_CELCIUS)

CONF_NAME = 'name'
DEFAULT_NAME = 'ZWave Thermostat'

REMOTEC = 0x5254
REMOTEC_ZXT_120 = 0x8377
REMOTEC_ZXT_120_THERMOSTAT = (REMOTEC, REMOTEC_ZXT_120, 0)

WORKAROUND_ZXT_120 = 'zxt_120'

DEVICE_MAPPINGS = {
    REMOTEC_ZXT_120_THERMOSTAT: WORKAROUND_ZXT_120
}


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
        """Initialize the zwave thermostat."""
        from openzwave.network import ZWaveNetwork
        from pydispatch import dispatcher
        ZWaveDeviceEntity.__init__(self, value, DOMAIN)
        self._node = value.node
        self._target_temperature = None
        self._current_temperature = None
        self._current_operation = STATE_IDLE
        self._current_operation_state = STATE_IDLE
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
                    self._zxt_120 = 1

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
        for _, value in self._node.get_values(class_id=0x31).items():
            self._current_temperature = int(value.data)
            self._unit = value.units
        # COMMAND_CLASS_THERMOSTAT_OPERATING_STATE
        if self._zxt_120 == 1:
            for _, value in self._node.get_values(class_id=0x44).items():
                self._current_operation_state = value.data_as_string
        else:
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
            return TEMP_CELCIUS
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
        if self._zxt_120 == 1:
            # ZXT-120 does not support get setpoint
            self._target_temperature = temperature
            if self._current_operation == 'Heat':
                for value in self._node.get_values(class_id=0x43).values():
                    if value.command_class == 67 and value.index == 1:
                        # ZXT-120 only responds to whole int
                        value.data = int(round(temperature, 0))
            elif self._current_operation == 'Cool':
                if value.command_class == 67 and value.index == 2:
                    value.data = int(round(temperature, 0))
            elif self._current_operation == 'Dry Air':
                if value.command_class == 67 and value.index == 8:
                    value.data = int(round(temperature, 0))
            elif self._current_operation == 'Auto Changeover':
                if value.command_class == 67 and value.index == 10:
                    value.data = int(round(temperature, 0))

        for _, value in self._node.get_values_for_command_class(0x43).items():
            if int(value.data) != 0:
                value.data = temperature
