"""
mysensors platform that offers a Climate(MySensors-HVAC) component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.mysensors

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
from homeassistant.components.climate import (
    STATE_COOL, STATE_HEAT, STATE_OFF, STATE_AUTO, ClimateDevice,
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW)
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_TEMPERATURE

_LOGGER = logging.getLogger(__name__)

DICT_HA_TO_MYS = {STATE_COOL: "CoolOn", STATE_HEAT: "HeatOn",
                  STATE_AUTO: "AutoChangeOver", STATE_OFF: "Off"}
DICT_MYS_TO_HA = {"CoolOn": STATE_COOL, "HeatOn": STATE_HEAT,
                  "AutoChangeOver": STATE_AUTO, "Off": STATE_OFF}

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors climate."""
    if discovery_info is None:
        return
    for gateway in mysensors.GATEWAYS.values():
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_HVAC: [set_req.V_HVAC_FLOW_STATE],
        }
        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, MySensorsHVAC))


# pylint: disable=too-many-arguments, too-many-public-methods
# pylint: disable=too-many-instance-attributes
class MySensorsHVAC(mysensors.MySensorsDeviceEntity, ClimateDevice):
    """Representation of a MySensorsHVAC hvac."""

    # def __init__(self, *args):
    #     """Setup instance attributes."""
    #     mysensors.MySensorsDeviceEntity.__init__(self, *args)
    #     self._state = None
    #     # Default Target Temperature set to a comfortable value of 24 degrees
    #     self._target_temperature = 24.0
    #     self._target_humidity = None
    #     self._away = None
    #     self._current_temperature = None
    #     self._current_humidity = None
    #     self._current_fan_mode = "Auto"
    #     self._current_operation = "Off"
    #     self._aux = None
    #     self._current_swing_mode = "Off"
    #     self._fan_list = ["Auto", "Min", "Normal", "Max"]
    #     self._operation_list = ["CoolOn", "Off"]
    #     self._swing_list = ["On", "Off"]

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return self.gateway.optimistic

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return (TEMP_CELSIUS
                if self.gateway.metric else TEMP_FAHRENHEIT)

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if len(self._values) != 0:
            return self._values[self.gateway.const.SetReq.V_TEMP]
        else: return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        #return self._target_temperature
        if len(self._values) != 0:
            return self._values[self.gateway.const.SetReq.V_HVAC_SETPOINT_COOL]
        else: return None

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        #return self._target_temperature
        if len(self._values) != 0:
            return self._values[self.gateway.const.SetReq.V_HVAC_SETPOINT_COOL]
        else: return None

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        #return self._target_temperature
        if len(self._values) != 0:
            return self._values[self.gateway.const.SetReq.V_HVAC_SETPOINT_COOL]
        else: return None

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if len(self._values) != 0:
            return self._values[self.gateway.const.SetReq.V_HVAC_FLOW_STATE]
        else: return STATE_OFF

    @property
    def operation_list(self):
        """List of available operation modes."""
        return [STATE_OFF, STATE_AUTO, STATE_COOL, STATE_HEAT]

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if len(self._values) != 0:
            return self._values[self.gateway.const.SetReq.V_HVAC_SPEED]
        else: return STATE_OFF

    @property
    def fan_list(self):
        """List of available fan modes."""
        return ["Auto", "Min", "Normal", "Max"]

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        _LOGGER.error(kwargs)
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            # Set HEAT Target temperature
            if self.current_operation == STATE_HEAT:
                self._values[set_req.V_HVAC_SETPOINT_HEAT] = kwargs.get(ATTR_TEMPERATURE)
                self.gateway.set_child_value(self.node_id, self.child_id,
                                             set_req.V_HVAC_SETPOINT_HEAT,
                                             kwargs.get(ATTR_TEMPERATURE))
            # Set COOL Target temperature
            elif self.current_operation == STATE_COOL:
                self._values[set_req.V_HVAC_SETPOINT_COOL] = kwargs.get(ATTR_TEMPERATURE)
                self.gateway.set_child_value(self.node_id, self.child_id,
                                             set_req.V_HVAC_SETPOINT_COOL,
                                             kwargs.get(ATTR_TEMPERATURE))
            # Set Both Target temperature for Auto Mode
            else:
                self._values[set_req.V_HVAC_SETPOINT_COOL] = kwargs.get(ATTR_TARGET_TEMP_HIGH)
                self.gateway.set_child_value(self.node_id, self.child_id,
                                             set_req.V_HVAC_SETPOINT_COOL,
                                             kwargs.get(ATTR_TEMPERATURE))
                self._values[set_req.V_HVAC_SETPOINT_HEAT] = kwargs.get(ATTR_TARGET_TEMP_LOW)
                self.gateway.set_child_value(self.node_id, self.child_id,
                                             set_req.V_HVAC_SETPOINT_HEAT,
                                             kwargs.get(ATTR_TEMPERATURE))
        self.update_ha_state()

    def set_fan_mode(self, fan):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        self._values[set_req.V_HVAC_SPEED] = fan
        self.gateway.set_child_value(self.node_id, self.child_id,
                                     set_req.V_HVAC_SPEED, fan)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[set_req.V_HVAC_SPEED] = fan
        self.update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        self._values[self.gateway.const.SetReq.V_HVAC_FLOW_STATE] = operation_mode
        self.gateway.set_child_value(self.node_id, self.child_id,
                                     self.gateway.const.SetReq.V_HVAC_FLOW_STATE,
                                     DICT_HA_TO_MYS[operation_mode])
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[self.gateway.const.SetReq.V_HVAC_FLOW_STATE] = operation_mode
        self.update_ha_state()

    def update(self):
        """Update the controller with the latest value from a sensor."""
        set_req = self.gateway.const.SetReq
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        for value_type, value in child.values.items():
            _LOGGER.debug(
                '%s: value_type %s, value = %s', self._name, value_type, value)
            if value_type == set_req.V_HVAC_FLOW_STATE:
                self._values[value_type] = DICT_MYS_TO_HA[value]
            else:
                self._values[value_type] = value

    def set_humidity(self, humidity):
        """Set new target humidity."""
        _LOGGER.error("Service Not Implemented yet")

    def set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        _LOGGER.error("Service Not Implemented yet")

    def turn_away_mode_on(self):
        """Turn away mode on."""
        _LOGGER.error("Service Not Implemented yet")

    def turn_away_mode_off(self):
        """Turn away mode off."""
        _LOGGER.error("Service Not Implemented yet")

    def turn_aux_heat_on(self):
        """Turn auxillary heater on."""
        _LOGGER.error("Service Not Implemented yet")

    def turn_aux_heat_off(self):
        """Turn auxillary heater off."""
        _LOGGER.error("Service Not Implemented yet")
