"""
Support for HomematicIP climate.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/climate.homematicip_cloud/
"""

import logging

from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, ATTR_TEMPERATURE,
    STATE_AUTO, STATE_MANUAL)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice, DOMAIN as HOMEMATICIP_CLOUD_DOMAIN,
    ATTR_HOME_ID)

_LOGGER = logging.getLogger(__name__)

STATE_BOOST = 'Boost'

HA_STATE_TO_HMIP = {
    STATE_AUTO: 'AUTOMATIC',
    STATE_MANUAL: 'MANUAL',
}

HMIP_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_HMIP.items()}


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
            devices.append(HomematicipHeatingGroup(home, device))

    if devices:
        async_add_devices(devices)


class HomematicipHeatingGroup(HomematicipGenericDevice, ClimateDevice):
    """Representation of a MomematicIP heating group."""

    def __init__(self, home, device):
        """Initialize heating group."""
        device.modelType = 'Group-Heating'
        super().__init__(home, device)

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

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
    def current_operation(self):
        """Return current operation ie. automatic or manual."""
        return HMIP_STATE_TO_HA.get(self._device.controlMode)

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
