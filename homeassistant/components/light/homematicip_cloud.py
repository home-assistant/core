"""
Support for HomematicIP light.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.homematicip_cloud/
"""

import logging

from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS)
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
        AsyncBrandSwitchMeasuring, AsyncDimmer)

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, AsyncBrandSwitchMeasuring):
            devices.append(HomematicipLightMeasuring(home, device))
        elif isinstance(device, AsyncDimmer):
            devices.append(HomematicipDimmer(home, device))

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


class HomematicipDimmer(HomematicipGenericDevice, Light):
    """MomematicIP dimmer light device."""

    def __init__(self, home, device):
        """Initialize the dimmer light device."""
        super().__init__(home, device)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.dimLevel != 0

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._device.dimLevel*255)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            await self._device.set_dim_level(
                kwargs[ATTR_BRIGHTNESS]/255.0)
        else:
            await self._device.set_dim_level(1)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self._device.set_dim_level(0)
