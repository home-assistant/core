"""Support for HomematicIP Cloud switches."""
import logging

from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice)
from homeassistant.components.switch import SwitchDevice

DEPENDENCIES = ['homematicip_cloud']

_LOGGER = logging.getLogger(__name__)

ATTR_POWER_CONSUMPTION = 'power_consumption'
ATTR_ENERGIE_COUNTER = 'energie_counter'
ATTR_PROFILE_MODE = 'profile_mode'


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud switch devices."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the HomematicIP switch from a config entry."""
    from homematicip.device import (
        PlugableSwitch,
        PlugableSwitchMeasuring,
        BrandSwitchMeasuring,
        FullFlushSwitchMeasuring,
    )

    from homematicip.group import SwitchingGroup

    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, BrandSwitchMeasuring):
            # BrandSwitchMeasuring inherits PlugableSwitchMeasuring
            # This device is implemented in the light platform and will
            # not be added in the switch platform
            pass
        elif isinstance(device, (PlugableSwitchMeasuring,
                                 FullFlushSwitchMeasuring)):
            devices.append(HomematicipSwitchMeasuring(home, device))
        elif isinstance(device, PlugableSwitch):
            devices.append(HomematicipSwitch(home, device))

    for group in home.groups:
        if isinstance(group, SwitchingGroup):
            devices.append(
                HomematicipGroupSwitch(home, group))

    if devices:
        async_add_entities(devices)


class HomematicipSwitch(HomematicipGenericDevice, SwitchDevice):
    """representation of a HomematicIP Cloud switch device."""

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


class HomematicipGroupSwitch(HomematicipGenericDevice, SwitchDevice):
    """representation of a HomematicIP switching group."""

    def __init__(self, home, device, post='Group'):
        """Initialize switching group."""
        device.modelType = 'HmIP-{}'.format(post)
        super().__init__(home, device, post)

    @property
    def is_on(self):
        """Return true if group is on."""
        return self._device.on

    async def async_turn_on(self, **kwargs):
        """Turn the group on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the group off."""
        await self._device.turn_off()


class HomematicipSwitchMeasuring(HomematicipSwitch):
    """Representation of a HomematicIP measuring switch device."""

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
