"""
Platform for a Mitsubishi Controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.mitsubishicontroller/
"""

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA,
                                              SUPPORT_TARGET_TEMPERATURE,
                                              SUPPORT_FAN_MODE,
                                              SUPPORT_OPERATION_MODE,
                                              SUPPORT_SWING_MODE,
                                              ATTR_FAN_MODE)
from homeassistant.const import CONF_URL, ATTR_TEMPERATURE
from homeassistant.const import TEMP_FAHRENHEIT

"""pypi requirements"""
REQUIREMENTS = ['mitsPy==0.1.9']

"""config params"""
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_URL): cv.string
})


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """setup platform asynchronously"""
    from mitsPy.manager import Manager
    controller = Manager(config.get(CONF_URL))

    async def register_devices(raw_devices):
        async_add_devices(
            [MitsubishiHvacDevice(
                device=device,
                unit_of_measurement=TEMP_FAHRENHEIT) for
                device in raw_devices]
        )

    await controller.initialize(register_devices)


"""supported features, for now all units will show the same features"""
SUPPORT_FLAGS = (
    SUPPORT_TARGET_TEMPERATURE
    | SUPPORT_OPERATION_MODE
    | SUPPORT_FAN_MODE
    | SUPPORT_SWING_MODE
)


class MitsubishiHvacDevice(ClimateDevice):
    """Mitsubishi HVAC Device"""

    def __init__(self, device, unit_of_measurement=None,
                 current_fan_mode=None):
        """initialize device"""
        self._device = device
        self._name = self._device.group_name
        self._current_swing_mode = self._device.current_air_direction
        self._unit_of_measurement = unit_of_measurement
        self._current_fan_mode = current_fan_mode
        self._device.refresh(self.schedule_update_ha_state)

    async def _refresh(self):
        """refresh function"""
        await self._device.refresh(self.schedule_update_ha_state)

    @property
    def should_poll(self):
        """should poll"""
        return True

    @property
    def name(self):
        """device name"""
        return self._name

    @property
    def unit_of_measurement(self):
        """unit of measurement"""
        return self._unit_of_measurement

    @property
    def temperature_unit(self):
        """temperature unit"""
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        """current temperature"""
        return float(self._device.current_temp_f)

    @property
    def target_temperature(self):
        """target temperature"""
        return float(self._device.set_temp_value_f)

    @property
    def state(self):
        """current state"""
        return self.current_operation

    @property
    def current_operation(self):
        """current operation mode"""
        return self._device.current_operation

    @property
    def operation_list(self):
        """list of supported operations"""
        return self._device.operation_list

    @property
    def current_fan_mode(self):
        """current fan mode"""
        return self._device.current_fan_speed

    @property
    def fan_list(self):
        """list of supported fan modes"""
        return self._device.fan_speed_options

    async def async_set_temperature(self, **kwargs):
        """set the temperature"""
        await self._device.set_temperature_f(kwargs[ATTR_TEMPERATURE])
        await self._refresh()

    async def async_set_swing_mode(self, swing_mode):
        """set the swing mode"""
        await self._device.set_air_direction(swing_mode)
        await self._refresh()

    async def async_set_fan_mode(self, fan):
        """set the fan mode"""
        await self._device.set_fan_speed(fan)
        await self._refresh()

    async def async_set_operation_mode(self, operation_mode, **kwargs):
        """set the operation mode"""
        await self._device.set_operation(operation_mode)
        await self._refresh()

    @property
    def current_swing_mode(self):
        """get the current swing mode"""
        return self._device.current_air_direction

    @property
    def swing_list(self):
        """get the list of available swing lists"""
        return self._device.air_direction_options

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    async def async_update(self):
        """update"""
        await self._device.refresh(self.schedule_update_ha_state)
