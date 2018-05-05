"""
Support for HomematicIP light.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.homematicip_cloud/
"""

import logging

from homeassistant.components.light import Light
from homeassistant.components.homematicip_cloud import (
    HomematicipGenericDevice, DOMAIN as HOMEMATICIP_CLOUD_DOMAIN,
    ATTR_HOME_ID)

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)

ATTR_POWER_CONSUMPTION = 'power_consumption'
ATTR_ENERGIE_COUNTER = 'energie_counter'
ATTR_PROFILE_MODE = 'profile_mode'


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the HomematicIP light devices."""
    from homematicip.device import (
        BrandSwitchMeasuring)

    if discovery_info is None:
        return
    home = hass.data[HOMEMATICIP_CLOUD_DOMAIN][discovery_info[ATTR_HOME_ID]]
    devices = []
    for device in home.devices:
        if isinstance(device, BrandSwitchMeasuring):
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
    def current_power_w(self):
        """Return the current power usage in W."""
        return self._device.currentPowerConsumption

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        if self._device.energyCounter is None:
            return 0
        return round(self._device.energyCounter)
