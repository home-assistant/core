"""
mysensors platform that offers a Climate(MySensors-HVAC) component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/#climate

Curently supported operations:

set_temperature()    --> V_HVAC_SETPOINT_COOL, V_HVAC_SETPOINT_HEAT
set_operation_mode() --> V_HVAC_FLOW_STATE
set_fan_mode()       --> V_HVAC_SPEED

Pending:
humidity, away_mode, aux_heat, swing_mode

home-assistant/components/climate/mysensors.py
"""
import logging

from homeassistant.components import mysensors
from homeassistant.components.climate import ClimateDevice
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors climate."""
    if discovery_info is None:
        return
    for gateway in mysensors.GATEWAYS.values():
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_HVAC: [set_req.V_HVAC_SETPOINT_HEAT,
                          set_req.V_HVAC_SETPOINT_COOL,
                          set_req.V_HVAC_FLOW_STATE,
                          set_req.V_HVAC_FLOW_MODE, set_req.V_HVAC_SPEED],
        }
        device_class_map = {
            pres.S_HVAC: MySensorsHVAC,
        }
        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, device_class_map))


# pylint: disable=too-many-arguments, too-many-public-methods
# pylint: disable=too-many-instance-attributes
class MySensorsHVAC(mysensors.MySensorsDeviceEntity, ClimateDevice):
    """Representation of a MySensorsHVAC hvac."""

    def __init__(self, *args):
        """Setup instance attributes."""
        mysensors.MySensorsDeviceEntity.__init__(self, *args)
        self._state = None
        # Default Target Temperature set to a comfortable value of 24 degrees
        self._target_temperature = 24.0
        self._target_humidity = None
        self._away = None
        self._current_temperature = None
        self._current_humidity = None
        self._current_fan_mode = "Auto"
        self._current_operation = "Off"
        self._aux = None
        self._current_swing_mode = "Off"
        self._fan_list = ["Auto", "Min", "Normal", "Max"]
        self._operation_list = ["CoolOn", "Off"]
        self._swing_list = ["On", "Off"]

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return self.gateway.optimistic

    @property
    def should_poll(self):
        """Polling not needed."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return (TEMP_CELSIUS
                if self.gateway.metric else TEMP_FAHRENHEIT)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._current_humidity

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    @property
    def is_aux_heat_on(self):
        """Return true if away mode is on."""
        return self._aux

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    @property
    def fan_list(self):
        """List of available fan modes."""
        return self._fan_list

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.gateway.set_child_value(self.node_id, self.child_id,
                                     set_req.V_HVAC_SETPOINT_COOL,
                                     self._target_temperature)
        if self.gateway.optimistic:
            # optimistically assume that device has changed state
            self._values[set_req.V_HVAC_SETPOINT_COOL] = \
                            self._target_temperature
        self.update_ha_state()

    def set_humidity(self, humidity):
        """Set new target temperature."""
        self._target_humidity = humidity
        self.update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set new target temperature."""
        self._current_swing_mode = swing_mode
        self.update_ha_state()

    def set_fan_mode(self, fan):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        self._current_fan_mode = fan
        self.gateway.set_child_value(self.node_id, self.child_id,
                                     set_req.V_HVAC_SPEED, fan)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[set_req.V_HVAC_SPEED] = fan
        self.update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        self._current_operation = operation_mode
        self.gateway.set_child_value(self.node_id, self.child_id,
                                     set_req.V_HVAC_FLOW_STATE, operation_mode)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[set_req.V_HVAC_FLOW_STATE] = operation_mode
        self.update_ha_state()

    @property
    def current_swing_mode(self):
        """Return the swing setting."""
        return self._current_swing_mode

    @property
    def swing_list(self):
        """List of available swing modes."""
        return self._swing_list

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.update_ha_state()

    def turn_aux_heat_on(self):
        """Turn away auxillary heater on."""
        self._aux = True
        self.update_ha_state()

    def turn_aux_heat_off(self):
        """Turn auxillary heater off."""
        self._aux = False
        self.update_ha_state()

    def update(self):
        """Update the controller with the latest value from a sensor."""
        set_req = self.gateway.const.SetReq
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        for value_type, value in child.values.items():
            _LOGGER.debug(
                '%s: value_type %s, value = %s', self._name, value_type, value)
            self._values[value_type] = value
        value_type = set_req.V_HVAC_FLOW_STATE
        if value_type in self._values:
            self._current_operation = self._values[value_type]
        value_type = set_req.V_HVAC_SPEED
        if value_type in self._values:
            self._current_fan_mode = self._values[value_type]
        value_type = set_req.V_HVAC_SETPOINT_COOL
        if value_type in self._values:
            self._target_temperature = self._values[value_type]
        value_type = set_req.V_TEMP
        if value_type in self._values:
            self._current_temperature = self._values[value_type]
