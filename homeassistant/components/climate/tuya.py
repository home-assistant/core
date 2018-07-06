"""
Support for the Tuya climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.tuya/
"""

import asyncio
from homeassistant.components.climate import (
    ATTR_TEMPERATURE, STATE_AUTO, STATE_COOL, STATE_ECO, STATE_ELECTRIC,
    STATE_FAN_ONLY, STATE_GAS, STATE_HEAT, STATE_HEAT_PUMP, STATE_HIGH_DEMAND,
    STATE_PERFORMANCE, SUPPORT_FAN_MODE, SUPPORT_ON_OFF,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
from homeassistant.components.fan import SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH
from homeassistant.components.tuya import DOMAIN, DATA_TUYA, TuyaDevice

from homeassistant.const import (
    PRECISION_WHOLE, STATE_OFF, STATE_ON, STATE_UNKNOWN, TEMP_CELSIUS,
    TEMP_FAHRENHEIT)

DEPENDENCIES = ['tuya']
DEVICE_TYPE = 'climate'

HA_STATE_TO_TUYA = {
    STATE_AUTO: 'auto',
    STATE_COOL: 'cold',
    STATE_ECO: 'eco',
    STATE_ELECTRIC: 'electric',
    STATE_FAN_ONLY: 'wind',
    STATE_GAS: 'gas',
    STATE_HEAT: 'hot',
    STATE_HEAT_PUMP: 'heat_pump',
    STATE_HIGH_DEMAND: 'high_demand',
    STATE_PERFORMANCE: 'performance',
}

TUYA_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_TUYA.items()}

FAN_MODES = {SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Tuya Climate devices."""
    tuya = hass.data[DATA_TUYA]
    devices = tuya.get_devices_by_type(DEVICE_TYPE)

    if DEVICE_TYPE not in hass.data[DOMAIN]['entities']:
        hass.data[DOMAIN]['entities'][DEVICE_TYPE] = []

    for device in devices:
        if device.object_id() not in hass.data[DOMAIN]['dev_ids']:
            add_devices([TuyaClimateDevice(device, hass)])
            hass.data[DOMAIN]['dev_ids'].append(device.object_id())


class TuyaClimateDevice(TuyaDevice, ClimateDevice):
    """Tuya climate devices,include air conditioner,heater."""

    def __init__(self, tuya, hass):
        """Init climate device."""
        super(TuyaClimateDevice, self).__init__(tuya, hass)
        self.entity_id = DEVICE_TYPE + '.' + tuya.object_id()

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities'][DEVICE_TYPE].append(self)

    @property
    def state(self):
        """Return the current state."""
        if self.is_on is False:
            return STATE_OFF
        if self.current_operation:
            return self.current_operation
        if self.is_on:
            return STATE_ON
        return STATE_UNKNOWN

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement to display."""
        return self.hass.config.units.temperature_unit

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        unit = self.tuya.temperature_unit()
        if unit == 'CELSIUS':
            return TEMP_CELSIUS
        elif unit == 'FAHRENHEIT':
            return TEMP_FAHRENHEIT
        else:
            return TEMP_CELSIUS

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self.tuya.current_humidity()

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self.tuya.target_humidity()

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        mode = self.tuya.current_operation()
        if mode is None:
            return None
        else:
            return TUYA_STATE_TO_HA.get(mode)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        modes = self.tuya.operation_list()
        operation_list = []
        for mode in modes:
            operation_list.append(TUYA_STATE_TO_HA.get(mode))
        return operation_list

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.tuya.current_temperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.tuya.target_temperature()

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.tuya.target_temperature_step()

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self.tuya.current_fan_mode()

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self.tuya.fan_list()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        self.tuya.set_temperature(temperature)

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self.tuya.set_fan_mode(fan_mode)

    def set_operation_mode(self, operation_mode):
        """Set new target operation mode."""
        self.tuya.set_operation_mode(HA_STATE_TO_TUYA.get(operation_mode))

    def turn_on(self):
        """Turn device on."""
        self.tuya.turn_on()

    def turn_off(self):
        """Turn device off."""
        self.tuya.turn_off()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supports = SUPPORT_ON_OFF
        if self.tuya.support_target_temperature():
            supports = supports | SUPPORT_TARGET_TEMPERATURE
        if self.tuya.support_mode():
            supports = supports | SUPPORT_OPERATION_MODE
        if self.tuya.support_wind_speed():
            supports = supports | SUPPORT_FAN_MODE
        return supports

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.tuya.min_temp()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.tuya.max_temp()
