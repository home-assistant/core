"""
Support for HomematicIP climate.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/climate.homematicip_cloud/
"""

import logging

from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE
from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice, DOMAIN as HOMEMATICIP_CLOUD_DOMAIN,
    ATTR_HOME_ID)

_LOGGER = logging.getLogger(__name__)

STATE_BOOST = 'Boost'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the HomematicIP climate devices."""
    from homematicip.group import HeatingGroup

    if discovery_info is None:
        return
    home = hass.data[HOMEMATICIP_CLOUD_DOMAIN][discovery_info[ATTR_HOME_ID]]

    devices = []
    for device in home.groups:
        if isinstance(device, HeatingGroup):
            devices.append(HomematicipHeatingGroup(hass, home, device))

    if devices:
        async_add_devices(devices)


class HomematicipHeatingGroup(HomematicipGenericDevice, ClimateDevice):
    """Representation of a MomematicIP heating group."""

    def __init__(self, hass, home, device):
        """Initialize heating group."""
        device.modelType = 'Group'
        super().__init__(home, device)

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:thermostat'

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._device.setPointTemperature

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.actualTemperature

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._device.humidity

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._device.minTemperature

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._device.maxTemperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._device.set_point_temperature(temperature)

    @property
    def current_operation(self):
        """Return current operation (auto, manual, boost, vacation)."""
        if self._device.boostMode:
            return STATE_BOOST
        elif self._device.controlMode == 'AUTOMATIC':
            return self._device.activeProfile.name
        return self._device.controlMode

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        modes = []
        for profile in self._device.profiles:
            if profile.name != '' and profile.enabled and profile.visible:
                modes.append(profile.name)
        modes.append(STATE_BOOST)
        return modes

    async def async_set_operation_mode(self, operation_mode):
        """Set operation mode."""
        if operation_mode == 'Boost':
            await self._device.set_boost()
        else:
            await self._device.set_boost(False)
            index = 0
            for profile in self._device.profiles:
                if profile.name == operation_mode:
                    await self._device.set_active_profile(index)
                    return
                index = index + 1
