"""
Support for control of ElkM1 connected thermostats.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.elkm1/
"""

from homeassistant.components.climate import (ATTR_TARGET_TEMP_HIGH,
                                              ATTR_TARGET_TEMP_LOW,
                                              PRECISION_WHOLE, STATE_AUTO,
                                              STATE_COOL, STATE_FAN_ONLY,
                                              STATE_HEAT, STATE_IDLE,
                                              SUPPORT_AUX_HEAT,
                                              SUPPORT_FAN_MODE,
                                              SUPPORT_OPERATION_MODE,
                                              SUPPORT_TARGET_TEMPERATURE_HIGH,
                                              SUPPORT_TARGET_TEMPERATURE_LOW,
                                              ClimateDevice)
from homeassistant.const import (STATE_ON, STATE_UNKNOWN)

from homeassistant.components.elkm1 import (DOMAIN, ElkDeviceBase,
                                            create_elk_devices)
from elkm1_lib.const import ThermostatFan, ThermostatMode, ThermostatSetting

DEPENDENCIES = [DOMAIN]

SUPPORT_FLAGS = (
    SUPPORT_TARGET_TEMPERATURE_HIGH | SUPPORT_TARGET_TEMPERATURE_LOW |
    SUPPORT_OPERATION_MODE | SUPPORT_FAN_MODE | SUPPORT_AUX_HEAT)


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info):
    """Setup the Elk switch platform."""
    elk = hass.data[DOMAIN]['elk']
    async_add_devices(create_elk_devices(hass, elk.thermostats, 'thermostat',
                                         ElkThermostat, []), True)
    return True


# pylint: disable=too-many-public-methods
class ElkThermostat(ElkDeviceBase, ClimateDevice):
    """Elk connected thermostat as Climate device."""
    def __init__(self, device, hass, config):
        """Initialize Thermostat."""
        ElkDeviceBase.__init__(self, 'climate', device, hass, config)

    # pylint: disable=unused-argument
    def _element_changed(self, element, changeset):
        pass

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._temperature_unit

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to display."""
        return self.temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._element.current_temp

    @property
    def state(self):
        """Return the current state."""
        # We can't actually tell if it's actively running in any of these
        # modes, just what mode is set
        if (self._element.mode == ThermostatMode.OFF.value) and (
                self._element.fan == ThermostatFan.ON.value):
            return STATE_FAN_ONLY
        if self._element.mode == ThermostatMode.OFF.value:
            return STATE_IDLE
        if (self._element.mode == ThermostatMode.HEAT.value) or (
                self._element.mode == ThermostatMode.EMERGENCY_HEAT.value):
            return STATE_HEAT
        if self._element.mode == ThermostatMode.COOL.value:
            return STATE_COOL
        if self._element.mode == ThermostatMode.AUTO.value:
            return STATE_AUTO
        return STATE_UNKNOWN

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._element.humidity

    @property
    def is_aux_heat_on(self):
        """Return true if aux heater."""
        return self._element.mode == ThermostatMode.EMERGENCY_HEAT.value

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if (self._element.mode == ThermostatMode.HEAT.value) or (
                self._element.mode == ThermostatMode.EMERGENCY_HEAT.value):
            return self._element.heat_setpoint
        if self._element.mode == ThermostatMode.COOL.value:
            return self._element.cool_setpoint
        return None

    @property
    def target_temperature_high(self):
        """Return the highbound target temperature we try to reach."""
        return self._element.cool_setpoint

    @property
    def target_temperature_low(self):
        """Return the lowbound target temperature we try to reach."""
        return self._element.heat_setpoint

    @property
    def min_temp(self):
        """Return the minimum temp supported."""
        return 1

    @property
    def max_temp(self):
        """Return the maximum temp supported."""
        return 99

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self.state

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return [STATE_IDLE, STATE_HEAT, STATE_COOL, STATE_AUTO, STATE_FAN_ONLY]

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if self._element.fan == ThermostatFan.AUTO.value:
            return STATE_AUTO
        if self._element.fan == ThermostatFan.ON.value:
            return STATE_ON
        return STATE_UNKNOWN

    def set_operation_mode(self, operation_mode):
        """Set mode."""
        if operation_mode == STATE_IDLE:
            self._element.set(ThermostatSetting.MODE.value,
                              ThermostatMode.OFF.value)
            self._element.set(ThermostatSetting.FAN.value,
                              ThermostatFan.AUTO.value)
        elif operation_mode == STATE_HEAT:
            self._element.set(ThermostatSetting.MODE.value,
                              ThermostatMode.HEAT.value)
            self._element.set(ThermostatSetting.FAN.value,
                              ThermostatFan.AUTO.value)
        elif operation_mode == STATE_COOL:
            self._element.set(ThermostatSetting.MODE.value,
                              ThermostatMode.COOL.value)
            self._element.set(ThermostatSetting.FAN.value,
                              ThermostatFan.AUTO.value)
        elif operation_mode == STATE_AUTO:
            self._element.set(ThermostatSetting.MODE.value,
                              ThermostatMode.AUTO.value)
            self._element.set(ThermostatSetting.FAN.value,
                              ThermostatFan.AUTO.value)
        elif operation_mode == STATE_FAN_ONLY:
            self._element.set(ThermostatSetting.MODE.value,
                              ThermostatMode.OFF.value)
            self._element.set(ThermostatSetting.FAN.value,
                              ThermostatFan.ON.value)

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        self._element.set(ThermostatSetting.MODE.value,
                          ThermostatMode.EMERGENCY_HEAT.value)
        self._element.set(ThermostatSetting.FAN.value,
                          ThermostatFan.AUTO.value)

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        self._element.set(ThermostatSetting.MODE.value,
                          ThermostatMode.HEAT.value)
        self._element.set(ThermostatSetting.FAN.value,
                          ThermostatFan.AUTO.value)

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return [STATE_AUTO, STATE_ON]

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode == STATE_AUTO:
            self._element.set(ThermostatSetting.FAN.value,
                              ThermostatFan.AUTO.value)
        elif fan_mode == STATE_ON:
            self._element.set(ThermostatSetting.FAN.value,
                              ThermostatFan.ON.value)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if low_temp is not None:
            low_temp = round(low_temp)
            self._element.set(ThermostatSetting.HEAT_SETPOINT.value, low_temp)
        if high_temp is not None:
            high_temp = round(high_temp)
            self._element.set(ThermostatSetting.COOL_SETPOINT.value, high_temp)
