"""
Support for HomematicIP light.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.homematicip_cloud/
"""

import logging

from homeassistant.components.light import Light
from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice, DOMAIN as HMIPC_DOMAIN,
    HMIPC_HAPID)

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)

ATTR_POWER_CONSUMPTION = 'power_consumption'
ATTR_ENERGIE_COUNTER = 'energie_counter_kwh'
ATTR_PROFILE_MODE = 'profile_mode'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Old way of setting up HomematicIP lights."""
    pass


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up the HomematicIP lights from a config entry."""
    from homematicip.aio.device import (
        AsyncBrandSwitchMeasuring)

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, AsyncBrandSwitchMeasuring):
            devices.append(HomematicipLightMeasuring(home, device))

    if devices:
        async_add_devices(devices)


class HomematicipLight(HomematicipGenericDevice, Light):
    """MomematicIP light device."""

    def __init__(self, home, device):
        """Initialize the light device."""
        super().__init__(home, device)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._device.turn_off()


class HomematicipLightMeasuring(HomematicipLight):
    """MomematicIP measuring light device."""

    @property
    def device_state_attributes(self):
        """Return the state attributes of the generic device."""
        attr = super().device_state_attributes
        if self._device.currentPowerConsumption > 0.05:
            attr.update({
                ATTR_POWER_CONSUMPTION:
                    round(self._device.currentPowerConsumption, 2)
            })
        attr.update({
            ATTR_ENERGIE_COUNTER: round(self._device.energyCounter, 2)
        })
        return attr
