"""Support for HomematicIP Cloud switches."""
import logging

from homematicip.aio.device import (
    AsyncBrandSwitchMeasuring, AsyncFullFlushSwitchMeasuring, AsyncMultiIOBox,
    AsyncOpenCollector8Module, AsyncPlugableSwitch,
    AsyncPlugableSwitchMeasuring)
from homematicip.aio.group import AsyncSwitchingGroup
from homematicip.aio.home import AsyncHome

from homeassistant.components.switch import SwitchDevice
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN as HMIPC_DOMAIN, HMIPC_HAPID, HomematicipGenericDevice
from .device import ATTR_GROUP_MEMBER_UNREACHABLE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the HomematicIP Cloud switch devices."""
    pass


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry,
                            async_add_entities) -> None:
    """Set up the HomematicIP switch from a config entry."""
    home = hass.data[HMIPC_DOMAIN][config_entry.data[HMIPC_HAPID]].home
    devices = []
    for device in home.devices:
        if isinstance(device, AsyncBrandSwitchMeasuring):
            # BrandSwitchMeasuring inherits PlugableSwitchMeasuring
            # This device is implemented in the light platform and will
            # not be added in the switch platform
            pass
        elif isinstance(device, (AsyncPlugableSwitchMeasuring,
                                 AsyncFullFlushSwitchMeasuring)):
            devices.append(HomematicipSwitchMeasuring(home, device))
        elif isinstance(device, AsyncPlugableSwitch):
            devices.append(HomematicipSwitch(home, device))
        elif isinstance(device, AsyncOpenCollector8Module):
            for channel in range(1, 9):
                devices.append(HomematicipMultiSwitch(home, device, channel))
        elif isinstance(device, AsyncMultiIOBox):
            for channel in range(1, 3):
                devices.append(HomematicipMultiSwitch(home, device, channel))

    for group in home.groups:
        if isinstance(group, AsyncSwitchingGroup):
            devices.append(
                HomematicipGroupSwitch(home, group))

    if devices:
        async_add_entities(devices)


class HomematicipSwitch(HomematicipGenericDevice, SwitchDevice):
    """representation of a HomematicIP Cloud switch device."""

    def __init__(self, home: AsyncHome, device) -> None:
        """Initialize the switch device."""
        super().__init__(home, device)

    @property
    def is_on(self) -> bool:
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

    def __init__(self, home: AsyncHome, device, post: str = 'Group') -> None:
        """Initialize switching group."""
        device.modelType = 'HmIP-{}'.format(post)
        super().__init__(home, device, post)

    @property
    def is_on(self) -> bool:
        """Return true if group is on."""
        return self._device.on

    @property
    def available(self) -> bool:
        """Switch-Group available."""
        # A switch-group must be available, and should not be affected by the
        # individual availability of group members.
        # This allows switching even when individual group members
        # are not available.
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes of the switch-group."""
        attr = {}
        if self._device.unreach:
            attr[ATTR_GROUP_MEMBER_UNREACHABLE] = True
        return attr

    async def async_turn_on(self, **kwargs):
        """Turn the group on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs):
        """Turn the group off."""
        await self._device.turn_off()


class HomematicipSwitchMeasuring(HomematicipSwitch):
    """Representation of a HomematicIP measuring switch device."""

    @property
    def current_power_w(self) -> float:
        """Return the current power usage in W."""
        return self._device.currentPowerConsumption

    @property
    def today_energy_kwh(self) -> int:
        """Return the today total energy usage in kWh."""
        if self._device.energyCounter is None:
            return 0
        return round(self._device.energyCounter)


class HomematicipMultiSwitch(HomematicipGenericDevice, SwitchDevice):
    """Representation of a HomematicIP Cloud multi switch device."""

    def __init__(self, home: AsyncHome, device, channel: int):
        """Initialize the multi switch device."""
        self.channel = channel
        super().__init__(home, device, 'Channel{}'.format(channel))

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "{}_{}_{}".format(self.__class__.__name__,
                                 self.post, self._device.id)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.functionalChannels[self.channel].on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._device.turn_on(self.channel)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._device.turn_off(self.channel)
