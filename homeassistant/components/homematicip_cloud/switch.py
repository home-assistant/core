"""Support for HomematicIP Cloud switches."""

from typing import Any, override

from homematicip.base.enums import DeviceType, FunctionalChannelType
from homematicip.group import ExtendedLinkedSwitchingGroup, SwitchingGroup

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ATTR_GROUP_MEMBER_UNREACHABLE, HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP

SWITCH_CHANNEL_TYPES = (
    FunctionalChannelType.SWITCH_CHANNEL,
    FunctionalChannelType.SWITCH_MEASURING_CHANNEL,
    FunctionalChannelType.MULTI_MODE_INPUT_SWITCH_CHANNEL,
)

# these carry a switch channel, but their entity is a light
LIGHT_OWNED_DEVICE_TYPES = (
    DeviceType.BRAND_SWITCH_NOTIFICATION_LIGHT,
    DeviceType.BRAND_SWITCH_MEASURING,
)

# a single channel, but named after it, so renaming would break their entity ids
CHANNEL_NAMED_DEVICE_TYPES = (DeviceType.DIN_RAIL_SWITCH,)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP switch from a config entry."""
    hap = config_entry.runtime_data
    entities: list[HomematicipGenericEntity] = [
        HomematicipGroupSwitch(hap, group)
        for group in hap.home.groups
        if isinstance(group, (ExtendedLinkedSwitchingGroup, SwitchingGroup))
    ]
    for device in hap.home.devices:
        device_type = getattr(device, "deviceType", None)
        if device_type in LIGHT_OWNED_DEVICE_TYPES:
            continue
        channels = [
            channel
            for channel in device.functionalChannels
            if channel.functionalChannelType in SWITCH_CHANNEL_TYPES
        ]
        # a lone channel is the device itself, so it keeps the device name
        is_multi_channel = (
            len(channels) > 1 or device_type in CHANNEL_NAMED_DEVICE_TYPES
        )
        entities.extend(
            HomematicipMultiSwitch(
                hap,
                device,
                channel=channel.index,
                channel_real_index=channel.index,
                is_multi_channel=is_multi_channel,
            )
            for channel in channels
        )

    async_add_entities(entities)


class HomematicipMultiSwitch(HomematicipGenericEntity, SwitchEntity):
    """Representation of the HomematicIP multi switch."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        channel=1,
        channel_real_index=None,
        is_multi_channel=True,
    ) -> None:
        """Initialize the multi switch device."""
        super().__init__(
            hap,
            device,
            channel=channel,
            channel_real_index=channel_real_index,
            is_multi_channel=is_multi_channel,
            feature_id="switch",
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return true if switch is on."""
        channel = self.get_channel_or_raise()
        return channel.on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        channel = self.get_channel_or_raise()
        await channel.async_turn_on()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        channel = self.get_channel_or_raise()
        await channel.async_turn_off()


class HomematicipGroupSwitch(HomematicipGenericEntity, SwitchEntity):
    """Representation of the HomematicIP switching group."""

    _attr_has_entity_name = False

    def __init__(self, hap: HomematicipHAP, device, post: str = "Group") -> None:
        """Initialize switching group."""
        device.modelType = f"HmIP-{post}"
        super().__init__(hap, device, post, feature_id="switch")

    @property
    @override
    def is_on(self) -> bool:
        """Return true if group is on."""
        return self._device.on

    @property
    @override
    def available(self) -> bool:
        """Switch-Group available."""
        # A switch-group must be available, and should not be affected by the
        # individual availability of group members.
        # This allows switching even when individual group members
        # are not available.
        return True

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the switch-group."""
        state_attr = super().extra_state_attributes

        if self._device.unreach:
            state_attr[ATTR_GROUP_MEMBER_UNREACHABLE] = True

        return state_attr

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the group on."""
        await self._device.turn_on_async()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the group off."""
        await self._device.turn_off_async()
