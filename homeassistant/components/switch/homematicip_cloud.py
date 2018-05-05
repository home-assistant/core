"""
Support for HomematicIP switch.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.homematicip_cloud/
"""

import logging

from homeassistant.components.switch import SwitchDevice
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
    """Set up the HomematicIP switch devices."""
    from homematicip.device import (
        PlugableSwitch, PlugableSwitchMeasuring,
        BrandSwitchMeasuring)

    if discovery_info is None:
        return
    home = hass.data[HOMEMATICIP_CLOUD_DOMAIN][discovery_info[ATTR_HOME_ID]]
    devices = []
    for device in home.devices:
        if isinstance(device, BrandSwitchMeasuring):
            # BrandSwitchMeasuring inherits PlugableSwitchMeasuring
            # This device is implemented in the light platform and will
            # not be added in the switch platform
            pass
        elif isinstance(device, PlugableSwitchMeasuring):
            devices.append(HomematicipSwitchMeasuring(home, device))
        elif isinstance(device, PlugableSwitch):
            devices.append(HomematicipSwitch(home, device))

    if devices:
        async_add_devices(devices)


class HomematicipSwitch(HomematicipGenericDevice, SwitchDevice):
    """MomematicIP switch device."""

    def __init__(self, home, device):
        """Initialize the switch device."""
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


class HomematicipSwitchMeasuring(HomematicipSwitch):
    """MomematicIP measuring switch device."""

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
