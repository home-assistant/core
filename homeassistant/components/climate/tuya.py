"""
Support for the Tuya climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.tuya/
"""

from homeassistant.components.climate import (
    ATTR_TEMPERATURE, ENTITY_ID_FORMAT, STATE_AUTO, STATE_COOL, STATE_ECO,
    STATE_ELECTRIC, STATE_FAN_ONLY, STATE_GAS, STATE_HEAT, STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND, STATE_PERFORMANCE, SUPPORT_FAN_MODE, SUPPORT_ON_OFF,
    SUPPORT_OPERATION_MODE, SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
from homeassistant.components.fan import SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH
from homeassistant.components.tuya import DATA_TUYA, TuyaDevice

from homeassistant.const import (
    PRECISION_WHOLE, TEMP_CELSIUS, TEMP_FAHRENHEIT)

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tuya Climate devices."""
    if discovery_info is None:
        return
    tuya = hass.data[DATA_TUYA]
    dev_ids = discovery_info.get('dev_ids')
    devices = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(TuyaClimateDevice(device))
    add_entities(devices)


class TuyaClimateDevice(TuyaDevice, ClimateDevice):
    """Tuya climate devices,include air conditioner,heater."""

    def __init__(self, tuya):
        """Init climate device."""
        super().__init__(tuya)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())
        self.operations = []

    async def async_added_to_hass(self):
        """Create operation list when add to hass."""
        await super().async_added_to_hass()
        modes = self.tuya.operation_list()
        if modes is None:
            return
        for mode in modes:
            if mode in TUYA_STATE_TO_HA:
                self.operations.append(TUYA_STATE_TO_HA[mode])

    @property
    def is_on(self):
        """Return true if climate is on."""
        return self.tuya.state()

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        unit = self.tuya.temperature_unit()
        if unit == 'CELSIUS':
            return TEMP_CELSIUS
        if unit == 'FAHRENHEIT':
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        mode = self.tuya.current_operation()
        if mode is None:
            return None
        return TUYA_STATE_TO_HA.get(mode)

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self.operations

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
        if ATTR_TEMPERATURE in kwargs:
            self.tuya.set_temperature(kwargs[ATTR_TEMPERATURE])

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
