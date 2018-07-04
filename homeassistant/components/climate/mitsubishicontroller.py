import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA,
                                              SUPPORT_TARGET_TEMPERATURE,
                                              SUPPORT_FAN_MODE,
                                              SUPPORT_OPERATION_MODE,
                                              SUPPORT_SWING_MODE)
from homeassistant.const import CONF_URL
from homeassistant.const import TEMP_FAHRENHEIT

REQUIREMENTS = ['mitsPy==0.1.9']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string
})


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    from mitsPy.manager import Manager
    controller = Manager(config.get(CONF_URL))

    async def register_devices(raw_devices):
        async_add_devices(
            [MitsubishiHvacDevice(device=device,
                                  unit_of_measurement=TEMP_FAHRENHEIT) for
             device in raw_devices])

    await controller.initialize(register_devices)


SUPPORT_FLAGS = (
        SUPPORT_TARGET_TEMPERATURE |
        SUPPORT_OPERATION_MODE |
        SUPPORT_FAN_MODE |
        SUPPORT_SWING_MODE
)


class MitsubishiHvacDevice(ClimateDevice):
    def __init__(self, device, unit_of_measurement=None,
                 current_fan_mode=None):
        self._device = device
        self._name = self._device.group_name
        self._current_swing_mode = self._device.current_air_direction
        self._unit_of_measurement = unit_of_measurement
        self._current_fan_mode = current_fan_mode
        self._device.refresh(self.schedule_update_ha_state)

    async def _refresh(self):
        await self._device.refresh(self.schedule_update_ha_state)

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
        return float(self._device.current_temp_f)

    @property
    def target_temperature(self):
        return float(self._device.set_temp_value_f)

    @property
    def state(self):
        return self.current_operation

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

    async def async_set_temperature(self, temperature, **kwargs):
        await self._device.set_temperature_f(temperature)
        await self._refresh()

    async def async_set_swing_mode(self, swing_mode):
        await self._device.set_air_direction(swing_mode)
        await self._refresh()

    async def async_set_fan_mode(self, fan):
        await self._device.set_fan_speed(fan)
        await self._refresh()

    async def async_set_operation_mode(self, operation_mode):
        await self._device.set_operation(operation_mode)
        await self._refresh()

    @property
    def current_swing_mode(self):
        return self._device.current_air_direction

    @property
    def swing_list(self):
        return self._device.air_direction_options

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def async_update(self):
        await self._device.refresh(self.schedule_update_ha_state)
