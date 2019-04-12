"""Support for control of Elk-M1 connected thermostats."""
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW, STATE_AUTO, STATE_COOL,
    STATE_FAN_ONLY, STATE_HEAT, STATE_IDLE, SUPPORT_AUX_HEAT, SUPPORT_FAN_MODE,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE_HIGH,
    SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import PRECISION_WHOLE, STATE_ON

from . import DOMAIN as ELK_DOMAIN, ElkEntity, create_elk_entities

DEPENDENCIES = [ELK_DOMAIN]


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Create the Elk-M1 thermostat platform."""
    if discovery_info is None:
        return

    elk = hass.data[ELK_DOMAIN]['elk']
    async_add_entities(create_elk_entities(
        hass, elk.thermostats, 'thermostat', ElkThermostat, []), True)


class ElkThermostat(ElkEntity, ClimateDevice):
    """Representation of an Elk-M1 Thermostat."""

    def __init__(self, element, elk, elk_data):
        """Initialize climate entity."""
        super().__init__(element, elk, elk_data)
        self._state = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (SUPPORT_OPERATION_MODE | SUPPORT_FAN_MODE | SUPPORT_AUX_HEAT
                | SUPPORT_TARGET_TEMPERATURE_HIGH
                | SUPPORT_TARGET_TEMPERATURE_LOW)

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return self._temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._element.current_temp

    @property
    def target_temperature(self):
        """Return the temperature we are trying to reach."""
        from elkm1_lib.const import ThermostatMode
        if (self._element.mode == ThermostatMode.HEAT.value) or (
                self._element.mode == ThermostatMode.EMERGENCY_HEAT.value):
            return self._element.heat_setpoint
        if self._element.mode == ThermostatMode.COOL.value:
            return self._element.cool_setpoint
        return None

    @property
    def target_temperature_high(self):
        """Return the high target temperature."""
        return self._element.cool_setpoint

    @property
    def target_temperature_low(self):
        """Return the low target temperature."""
        return self._element.heat_setpoint

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._element.humidity

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._state

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [STATE_IDLE, STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_FAN_ONLY]

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def is_aux_heat_on(self):
        """Return if aux heater is on."""
        from elkm1_lib.const import ThermostatMode
        return self._element.mode == ThermostatMode.EMERGENCY_HEAT.value

    @property
    def min_temp(self):
        """Return the minimum temperature supported."""
        return 1

    @property
    def max_temp(self):
        """Return the maximum temperature supported."""
        return 99

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        from elkm1_lib.const import ThermostatFan
        if self._element.fan == ThermostatFan.AUTO.value:
            return STATE_AUTO
        if self._element.fan == ThermostatFan.ON.value:
            return STATE_ON
        return None

    def _elk_set(self, mode, fan):
        from elkm1_lib.const import ThermostatSetting
        if mode is not None:
            self._element.set(ThermostatSetting.MODE.value, mode)
        if fan is not None:
            self._element.set(ThermostatSetting.FAN.value, fan)

    async def async_set_operation_mode(self, operation_mode):
        """Set thermostat operation mode."""
        from elkm1_lib.const import ThermostatFan, ThermostatMode
        settings = {
            STATE_IDLE: (ThermostatMode.OFF.value, ThermostatFan.AUTO.value),
            STATE_HEAT: (ThermostatMode.HEAT.value, None),
            STATE_COOL: (ThermostatMode.COOL.value, None),
            STATE_AUTO: (ThermostatMode.AUTO.value, None),
            STATE_FAN_ONLY: (ThermostatMode.OFF.value, ThermostatFan.ON.value)
        }
        self._elk_set(settings[operation_mode][0], settings[operation_mode][1])

    async def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        from elkm1_lib.const import ThermostatMode
        self._elk_set(ThermostatMode.EMERGENCY_HEAT.value, None)

    async def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        from elkm1_lib.const import ThermostatMode
        self._elk_set(ThermostatMode.HEAT.value, None)

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return [STATE_AUTO, STATE_ON]

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        from elkm1_lib.const import ThermostatFan
        if fan_mode == STATE_AUTO:
            self._elk_set(None, ThermostatFan.AUTO.value)
        elif fan_mode == STATE_ON:
            self._elk_set(None, ThermostatFan.ON.value)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        from elkm1_lib.const import ThermostatSetting
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if low_temp is not None:
            self._element.set(
                ThermostatSetting.HEAT_SETPOINT.value, round(low_temp))
        if high_temp is not None:
            self._element.set(
                ThermostatSetting.COOL_SETPOINT.value, round(high_temp))

    def _element_changed(self, element, changeset):
        from elkm1_lib.const import ThermostatFan, ThermostatMode
        mode_to_state = {
            ThermostatMode.OFF.value: STATE_IDLE,
            ThermostatMode.COOL.value: STATE_COOL,
            ThermostatMode.HEAT.value: STATE_HEAT,
            ThermostatMode.EMERGENCY_HEAT.value: STATE_HEAT,
            ThermostatMode.AUTO.value: STATE_AUTO,
        }
        self._state = mode_to_state.get(self._element.mode)
        if self._state == STATE_IDLE and \
                self._element.fan == ThermostatFan.ON.value:
            self._state = STATE_FAN_ONLY
