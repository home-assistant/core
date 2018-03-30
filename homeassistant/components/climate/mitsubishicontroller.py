import voluptuous as vol

import asyncio

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import ClimateDevice
from homeassistant.const import CONF_URL
from homeassistant.const import TEMP_FAHRENHEIT

DOMAIN = 'mitsubishicontroller'

from mitsPy.manager import Manager

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_URL): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    controller = Manager(config[CONF_URL], loop=hass.loop)
    controller.initialize(lambda raw_devices: async_add_devices(
        [MitsubishiHvacDevice(device=device, unit_of_measurement=TEMP_FAHRENHEIT) for device in raw_devices]))


class MitsubishiHvacDevice(ClimateDevice):
    def __init__(self, device, unit_of_measurement=None, current_fan_mode=None):
        self._device = device
        self._name = self._device.number + " : " + self._device.group_name
        self._current_swing_mode = self._device.current_air_direction
        self._unit_of_measurement = unit_of_measurement
        self._current_fan_mode = current_fan_mode
        self._device.refresh(self.schedule_update_ha_state)

    def _refresh(self):
        self._device.refresh(self.schedule_update_ha_state)

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._name

    @property
    def unit_of_measurement(self):
        return self._unit_of_measurement

    @property
    def temperature_unit(self):
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        return self._device.current_temp_f

    @property
    def target_temperature(self):
        return self._device.set_temp_value_f

    @property
    def current_operation(self):
        return self._device.current_operation

    @property
    def operation_list(self):
        return self._device.operation_list

    @property
    def current_fan_mode(self):
        return self._device.current_fan_speed

    @property
    def fan_list(self):
        return self._device.fan_speed_options

    def set_temperature(self, temperature, **kwargs):
        self._device.set_temperature_f(temperature)
        self._refresh()

    def set_swing_mode(self, swing_mode):
        self._device.set_air_direction(swing_mode)
        self._refresh()

    def set_fan_mode(self, fan):
        self._device.set_fan_speed(fan)
        self._refresh()

    def set_operation_mode(self, operation_mode):
        self._device.set_operation(operation_mode)
        self._refresh()

    @property
    def current_swing_mode(self):
        return self._device.current_air_direction

    @property
    def swing_list(self):
        return self._device.air_direction_options

    def update(self):
        self._device.refresh(self.schedule_update_ha_state)
