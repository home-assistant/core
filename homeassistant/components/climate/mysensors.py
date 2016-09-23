"""
mysensors platform that offers a Climate(MySensors-HVAC) component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.mysensors
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
        if float(gateway.protocol_version) < 1.5:
            continue
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_HVAC: [set_req.V_HVAC_FLOW_STATE],
        }
        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, MySensorsHVAC))


# pylint: disable=too-many-arguments, too-many-public-methods
class MySensorsHVAC(mysensors.MySensorsDeviceEntity, ClimateDevice):
    """Representation of a MySensorsHVAC hvac."""

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
        return self._values.get(self.gateway.const.SetReq.V_TEMP)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SETPOINT_COOL in self._values and \
                set_req.V_HVAC_SETPOINT_HEAT in self._values:
            return None
        temp = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
        if temp is None:
            temp = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
        return temp

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SETPOINT_HEAT in self._values:
            return self._values.get(set_req.V_HVAC_SETPOINT_COOL)

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        set_req = self.gateway.const.SetReq
        if set_req.V_HVAC_SETPOINT_COOL in self._values:
            return self._values.get(set_req.V_HVAC_SETPOINT_HEAT)

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._values.get(self.gateway.const.SetReq.V_HVAC_FLOW_STATE)

    @property
    def operation_list(self):
        """List of available operation modes."""
        return [STATE_OFF, STATE_AUTO, STATE_COOL, STATE_HEAT]

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._values.get(self.gateway.const.SetReq.V_HVAC_SPEED)

    @property
    def fan_list(self):
        """List of available fan modes."""
        return ["Auto", "Min", "Normal", "Max"]

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        temp = kwargs.get(ATTR_TEMPERATURE)
        low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        heat = self._values.get(set_req.V_HVAC_SETPOINT_HEAT)
        cool = self._values.get(set_req.V_HVAC_SETPOINT_COOL)
        updates = ()
        if temp is not None:
            if heat is not None:
                # Set HEAT Target temperature
                value_type = set_req.V_HVAC_SETPOINT_HEAT
            elif cool is not None:
                # Set COOL Target temperature
                value_type = set_req.V_HVAC_SETPOINT_COOL
            if heat is not None or cool is not None:
                updates = [(value_type, temp)]
        elif all(val is not None for val in (low, high, heat, cool)):
            updates = [
                (set_req.V_HVAC_SETPOINT_HEAT, low),
                (set_req.V_HVAC_SETPOINT_COOL, high)]
        for value_type, value in updates:
            self.gateway.set_child_value(
                self.node_id, self.child_id, value_type, value)
            if self.gateway.optimistic:
                # optimistically assume that switch has changed state
                self._values[value_type] = value
                self.update_ha_state()

    def set_fan_mode(self, fan):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(self.node_id, self.child_id,
                                     set_req.V_HVAC_SPEED, fan)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[set_req.V_HVAC_SPEED] = fan
            self.update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new target temperature."""
        set_req = self.gateway.const.SetReq
        self.gateway.set_child_value(self.node_id, self.child_id,
                                     set_req.V_HVAC_FLOW_STATE,
                                     DICT_HA_TO_MYS[operation_mode])
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[set_req.V_HVAC_FLOW_STATE] = operation_mode
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
