"""Support for HomematicIP Cloud switches."""
from typing import Any, Dict

from homematicip.aio.device import (
    AsyncBrandSwitchMeasuring,
    AsyncFullFlushInputSwitch,
    AsyncFullFlushSwitchMeasuring,
    AsyncHeatingSwitch2,
    AsyncMultiIOBox,
    AsyncOpenCollector8Module,
    AsyncPlugableSwitch,
    AsyncPlugableSwitchMeasuring,
    AsyncPrintedCircuitBoardSwitch2,
    AsyncPrintedCircuitBoardSwitchBattery,
    AsyncWiredSwitch8,
)
from homematicip.aio.group import AsyncExtendedLinkedSwitchingGroup, AsyncSwitchingGroup

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericEntity
from .generic_entity import ATTR_GROUP_MEMBER_UNREACHABLE
from .hap import HomematicipHAP


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP switch from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities = []
    for device in hap.home.devices:
        if isinstance(device, AsyncBrandSwitchMeasuring):
            # BrandSwitchMeasuring inherits PlugableSwitchMeasuring
            # This entity is implemented in the light platform and will
            # not be added in the switch platform
            pass
        elif isinstance(
            device, (AsyncPlugableSwitchMeasuring, AsyncFullFlushSwitchMeasuring)
        ):
            entities.append(HomematicipSwitchMeasuring(hap, device))
        elif isinstance(device, AsyncWiredSwitch8):
            for channel in range(1, 9):
                entities.append(HomematicipMultiSwitch(hap, device, channel=channel))
        elif isinstance(
            device,
            (
                AsyncPlugableSwitch,
                AsyncPrintedCircuitBoardSwitchBattery,
                AsyncFullFlushInputSwitch,
            ),
        ):
            entities.append(HomematicipSwitch(hap, device))
        elif isinstance(device, AsyncOpenCollector8Module):
            for channel in range(1, 9):
                entities.append(HomematicipMultiSwitch(hap, device, channel=channel))
        elif isinstance(device, AsyncHeatingSwitch2):
            for channel in range(1, 3):
                entities.append(HomematicipMultiSwitch(hap, device, channel=channel))
        elif isinstance(device, AsyncMultiIOBox):
            for channel in range(1, 3):
                entities.append(HomematicipMultiSwitch(hap, device, channel=channel))
        elif isinstance(device, AsyncPrintedCircuitBoardSwitch2):
            for channel in range(1, 3):
                entities.append(HomematicipMultiSwitch(hap, device, channel=channel))

    for group in hap.home.groups:
        if isinstance(group, (AsyncExtendedLinkedSwitchingGroup, AsyncSwitchingGroup)):
            entities.append(HomematicipGroupSwitch(hap, group))

    if entities:
        async_add_entities(entities)


class HomematicipMultiSwitch(HomematicipGenericEntity, SwitchEntity):
    """Representation of the HomematicIP multi switch."""

    def __init__(self, hap: HomematicipHAP, device, channel: int) -> None:
        """Initialize the multi switch device."""
        super().__init__(hap, device, channel=channel)

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._device.functionalChannels[self._channel].on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self._device.turn_on(self._channel)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self._device.turn_off(self._channel)


class HomematicipSwitch(HomematicipGenericEntity, SwitchEntity):
    """Representation of the HomematicIP switch."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the switch device."""
        super().__init__(hap, device)

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.on

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the device on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        await self._device.turn_off()


class HomematicipGroupSwitch(HomematicipGenericEntity, SwitchEntity):
    """Representation of the HomematicIP switching group."""

    def __init__(self, hap: HomematicipHAP, device, post: str = "Group") -> None:
        """Initialize switching group."""
        device.modelType = f"HmIP-{post}"
        super().__init__(hap, device, post)

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
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the state attributes of the switch-group."""
        state_attr = super().device_state_attributes

        if self._device.unreach:
            state_attr[ATTR_GROUP_MEMBER_UNREACHABLE] = True

        return state_attr

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the group on."""
        await self._device.turn_on()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the group off."""
        await self._device.turn_off()


class HomematicipSwitchMeasuring(HomematicipSwitch):
    """Representation of the HomematicIP measuring switch."""

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
