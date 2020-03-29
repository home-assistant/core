"""Support for control of Elk-M1 connected thermostats."""
from elkm1_lib.const import ThermostatFan, ThermostatMode, ThermostatSetting

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import PRECISION_WHOLE, STATE_ON, TEMP_CELSIUS, TEMP_FAHRENHEIT

from . import ElkEntity, create_elk_entities
from .const import DOMAIN

SUPPORT_HVAC = [
    HVAC_MODE_OFF,
    HVAC_MODE_HEAT,
    HVAC_MODE_COOL,
    HVAC_MODE_AUTO,
    HVAC_MODE_FAN_ONLY,
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Create the Elk-M1 thermostat platform."""
    elk_data = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    elk = elk_data["elk"]
    create_elk_entities(
        elk_data, elk.thermostats, "thermostat", ElkThermostat, entities
    )
    async_add_entities(entities, True)


class ElkThermostat(ElkEntity, ClimateDevice):
    """Representation of an Elk-M1 Thermostat."""

    def __init__(self, element, elk, elk_data):
        """Initialize climate entity."""
        super().__init__(element, elk, elk_data)
        self._state = None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FAN_MODE | SUPPORT_AUX_HEAT | SUPPORT_TARGET_TEMPERATURE_RANGE

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return TEMP_FAHRENHEIT if self._temperature_unit == "F" else TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._element.current_temp

    @property
    def target_temperature(self):
        """Return the temperature we are trying to reach."""
        if (self._element.mode == ThermostatMode.HEAT.value) or (
            self._element.mode == ThermostatMode.EMERGENCY_HEAT.value
        ):
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
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        return self._state

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return SUPPORT_HVAC

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def is_aux_heat(self):
        """Return if aux heater is on."""
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
    def fan_mode(self):
        """Return the fan setting."""
        if self._element.fan == ThermostatFan.AUTO.value:
            return HVAC_MODE_AUTO
        if self._element.fan == ThermostatFan.ON.value:
            return STATE_ON
        return None

    def _elk_set(self, mode, fan):
        if mode is not None:
            self._element.set(ThermostatSetting.MODE.value, mode)
        if fan is not None:
            self._element.set(ThermostatSetting.FAN.value, fan)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set thermostat operation mode."""
        settings = {
            HVAC_MODE_OFF: (ThermostatMode.OFF.value, ThermostatFan.AUTO.value),
            HVAC_MODE_HEAT: (ThermostatMode.HEAT.value, None),
            HVAC_MODE_COOL: (ThermostatMode.COOL.value, None),
            HVAC_MODE_AUTO: (ThermostatMode.AUTO.value, None),
            HVAC_MODE_FAN_ONLY: (ThermostatMode.OFF.value, ThermostatFan.ON.value),
        }
        self._elk_set(settings[hvac_mode][0], settings[hvac_mode][1])

    async def async_turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self._elk_set(ThermostatMode.EMERGENCY_HEAT.value, None)

    async def async_turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._elk_set(ThermostatMode.HEAT.value, None)

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return [HVAC_MODE_AUTO, STATE_ON]

    async def async_set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode == HVAC_MODE_AUTO:
            self._elk_set(None, ThermostatFan.AUTO.value)
        elif fan_mode == STATE_ON:
            self._elk_set(None, ThermostatFan.ON.value)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if low_temp is not None:
            self._element.set(ThermostatSetting.HEAT_SETPOINT.value, round(low_temp))
        if high_temp is not None:
            self._element.set(ThermostatSetting.COOL_SETPOINT.value, round(high_temp))

    def _element_changed(self, element, changeset):
        mode_to_state = {
            ThermostatMode.OFF.value: HVAC_MODE_OFF,
            ThermostatMode.COOL.value: HVAC_MODE_COOL,
            ThermostatMode.HEAT.value: HVAC_MODE_HEAT,
            ThermostatMode.EMERGENCY_HEAT.value: HVAC_MODE_HEAT,
            ThermostatMode.AUTO.value: HVAC_MODE_AUTO,
        }
        self._state = mode_to_state.get(self._element.mode)
        if self._state == HVAC_MODE_OFF and self._element.fan == ThermostatFan.ON.value:
            self._state = HVAC_MODE_FAN_ONLY
