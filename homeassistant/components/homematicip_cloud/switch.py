"""Support for HomematicIP Cloud switches."""

from __future__ import annotations

from typing import Any

from homematicip.device import (
    BrandSwitch2,
    BrandSwitchMeasuring,
    DinRailSwitch,
    DinRailSwitch4,
    FullFlushInputSwitch,
    FullFlushSwitchMeasuring,
    HeatingSwitch2,
    MultiIOBox,
    OpenCollector8Module,
    PlugableSwitch,
    PlugableSwitchMeasuring,
    PrintedCircuitBoardSwitch2,
    PrintedCircuitBoardSwitchBattery,
    WiredSwitch8,
)
from homematicip.group import ExtendedLinkedSwitchingGroup, SwitchingGroup

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import ATTR_GROUP_MEMBER_UNREACHABLE, HomematicipGenericEntity
from .hap import HomematicipHAP


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP switch from a config entry."""
    hap = hass.data[DOMAIN][config_entry.unique_id]
    entities: list[HomematicipGenericEntity] = [
        HomematicipGroupSwitch(hap, group)
        for group in hap.home.groups
        if isinstance(group, (ExtendedLinkedSwitchingGroup, SwitchingGroup))
    ]
    for device in hap.home.devices:
        if isinstance(device, BrandSwitchMeasuring):
            # BrandSwitchMeasuring inherits PlugableSwitchMeasuring
            # This entity is implemented in the light platform and will
            # not be added in the switch platform
            pass
        elif isinstance(device, (PlugableSwitchMeasuring, FullFlushSwitchMeasuring)):
            entities.append(HomematicipSwitchMeasuring(hap, device))
        elif isinstance(device, WiredSwitch8):
            entities.extend(
                HomematicipMultiSwitch(hap, device, channel=channel)
                for channel in range(1, 9)
            )
        elif isinstance(device, DinRailSwitch):
            entities.append(HomematicipMultiSwitch(hap, device, channel=1))
        elif isinstance(device, DinRailSwitch4):
            entities.extend(
                HomematicipMultiSwitch(hap, device, channel=channel)
                for channel in range(1, 5)
            )
        elif isinstance(
            device,
            (
                PlugableSwitch,
                PrintedCircuitBoardSwitchBattery,
                FullFlushInputSwitch,
            ),
        ):
            entities.append(HomematicipSwitch(hap, device))
        elif isinstance(device, OpenCollector8Module):
            entities.extend(
                HomematicipMultiSwitch(hap, device, channel=channel)
                for channel in range(1, 9)
            )
        elif isinstance(
            device,
            (
                BrandSwitch2,
                PrintedCircuitBoardSwitch2,
                HeatingSwitch2,
                MultiIOBox,
            ),
        ):
            entities.extend(
                HomematicipMultiSwitch(hap, device, channel=channel)
                for channel in range(1, 3)
            )

    async_add_entities(entities)


class HomematicipMultiSwitch(HomematicipGenericEntity, SwitchEntity):
    """Representation of the HomematicIP multi switch."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        channel=1,
        is_multi_channel=True,
    ) -> None:
        """Initialize the multi switch device."""
        super().__init__(
            hap, device, channel=channel, is_multi_channel=is_multi_channel
        )

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._device.functionalChannels[self._channel].on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._device.turn_on_async(self._channel)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._device.turn_off_async(self._channel)


class HomematicipSwitch(HomematicipMultiSwitch, SwitchEntity):
    """Representation of the HomematicIP switch."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the switch device."""
        super().__init__(hap, device, is_multi_channel=False)


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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the switch-group."""
        state_attr = super().extra_state_attributes

        if self._device.unreach:
            state_attr[ATTR_GROUP_MEMBER_UNREACHABLE] = True

        return state_attr

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the group on."""
        await self._device.turn_on_async()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the group off."""
        await self._device.turn_off_async()


class HomematicipSwitchMeasuring(HomematicipSwitch):
    """Representation of the HomematicIP measuring switch."""
