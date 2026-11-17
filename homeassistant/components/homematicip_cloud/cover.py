"""Support for HomematicIP Cloud cover devices."""

from typing import Any, override

from homematicip.base.enums import DoorCommand, DoorState, FunctionalChannelType
from homematicip.group import ExtendedLinkedShutterGroup

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import HomematicipGenericEntity
from .hap import HomematicIPConfigEntry, HomematicipHAP

HMIP_COVER_OPEN = 0
HMIP_COVER_CLOSED = 1
HMIP_SLATS_OPEN = 0
HMIP_SLATS_CLOSED = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomematicIPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the HomematicIP cover from a config entry."""
    hap = config_entry.runtime_data
    entities: list[HomematicipGenericEntity] = [
        HomematicipCoverShutterGroup(hap, group)
        for group in hap.home.groups
        if isinstance(group, ExtendedLinkedShutterGroup)
    ]
    for device in hap.home.devices:
        for channel_types, entity_class in COVER_CHANNEL_TYPES:
            channels = [
                channel
                for channel in device.functionalChannels
                if channel.functionalChannelType in channel_types
            ]
            # a lone channel is the device itself, so it keeps the device name
            is_multi_channel = len(channels) > 1
            entities.extend(
                entity_class(
                    hap,
                    device,
                    channel=channel.index,
                    channel_real_index=channel.index,
                    is_multi_channel=is_multi_channel,
                )
                for channel in channels
            )

    async_add_entities(entities)


class HomematicipChannelCover(HomematicipGenericEntity, CoverEntity):
    """Representation of a HomematicIP cover channel."""

    _cover_feature_id: str

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        channel: int,
        channel_real_index: int,
        is_multi_channel: bool,
    ) -> None:
        """Initialize the cover channel entity."""
        super().__init__(
            hap,
            device,
            channel=channel,
            channel_real_index=channel_real_index,
            is_multi_channel=is_multi_channel,
            feature_id=self._cover_feature_id,
        )


class HomematicipBlindModule(HomematicipChannelCover):
    """Representation of the HomematicIP blind module."""

    _attr_device_class = CoverDeviceClass.BLIND

    _cover_feature_id = "blind"

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        channel = self.get_channel_or_raise()
        if channel.primaryShadingLevel is not None:
            return int((1 - channel.primaryShadingLevel) * 100)
        return None

    @property
    @override
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        channel = self.get_channel_or_raise()
        if channel.secondaryShadingLevel is not None:
            return int((1 - channel.secondaryShadingLevel) * 100)
        return None

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # HmIP cover is closed:1 -> open:0
        level = 1 - position / 100.0
        channel = self.get_channel_or_raise()
        await channel.async_set_primary_shading_level(primaryShadingLevel=level)

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        # HmIP slats is closed:1 -> open:0
        level = 1 - position / 100.0
        channel = self.get_channel_or_raise()
        await channel.async_set_secondary_shading_level(
            primaryShadingLevel=channel.primaryShadingLevel,
            secondaryShadingLevel=level,
        )

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        channel = self.get_channel_or_raise()
        if channel.primaryShadingLevel is not None:
            return channel.primaryShadingLevel == HMIP_COVER_CLOSED
        return None

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        channel = self.get_channel_or_raise()
        await channel.async_set_primary_shading_level(
            primaryShadingLevel=HMIP_COVER_OPEN
        )

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        channel = self.get_channel_or_raise()
        await channel.async_set_primary_shading_level(
            primaryShadingLevel=HMIP_COVER_CLOSED
        )

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        channel = self.get_channel_or_raise()
        await channel.async_set_shutter_stop()

    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the slats."""
        channel = self.get_channel_or_raise()
        await channel.async_set_secondary_shading_level(
            primaryShadingLevel=channel.primaryShadingLevel,
            secondaryShadingLevel=HMIP_SLATS_OPEN,
        )

    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the slats."""
        channel = self.get_channel_or_raise()
        await channel.async_set_secondary_shading_level(
            primaryShadingLevel=channel.primaryShadingLevel,
            secondaryShadingLevel=HMIP_SLATS_CLOSED,
        )

    @override
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        channel = self.get_channel_or_raise()
        await channel.async_set_shutter_stop()


class HomematicipMultiCoverShutter(HomematicipChannelCover):
    """Representation of the HomematicIP cover shutter."""

    _attr_device_class = CoverDeviceClass.SHUTTER

    _cover_feature_id = "shutter"

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        channel = self.get_channel_or_raise()
        if channel.shutterLevel is not None:
            return int((1 - channel.shutterLevel) * 100)
        return None

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # HmIP cover is closed:1 -> open:0
        level = 1 - position / 100.0
        channel = self.get_channel_or_raise()
        await channel.async_set_shutter_level(level)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        channel = self.get_channel_or_raise()
        if channel.shutterLevel is not None:
            return channel.shutterLevel == HMIP_COVER_CLOSED
        return None

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        channel = self.get_channel_or_raise()
        await channel.async_set_shutter_level(HMIP_COVER_OPEN)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        channel = self.get_channel_or_raise()
        await channel.async_set_shutter_level(HMIP_COVER_CLOSED)

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        channel = self.get_channel_or_raise()
        await channel.async_set_shutter_stop()


class HomematicipMultiCoverSlats(HomematicipMultiCoverShutter):
    """Representation of the HomematicIP multi cover slats."""

    _cover_feature_id = "slats"

    @property
    @override
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        channel = self.get_channel_or_raise()
        if channel.slatsLevel is not None:
            return int((1 - channel.slatsLevel) * 100)
        return None

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        # HmIP slats is closed:1 -> open:0
        level = 1 - position / 100.0
        channel = self.get_channel_or_raise()
        await channel.async_set_slats_level(slatsLevel=level)

    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the slats."""
        channel = self.get_channel_or_raise()
        await channel.async_set_slats_level(slatsLevel=HMIP_SLATS_OPEN)

    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the slats."""
        channel = self.get_channel_or_raise()
        await channel.async_set_slats_level(slatsLevel=HMIP_SLATS_CLOSED)

    @override
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        channel = self.get_channel_or_raise()
        await channel.async_set_shutter_stop()


class HomematicipGarageDoorModule(HomematicipChannelCover):
    """Representation of the HomematicIP Garage Door Module."""

    _attr_device_class = CoverDeviceClass.GARAGE

    _cover_feature_id = "garage_door"

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        door_state_to_position = {
            DoorState.CLOSED: 0,
            DoorState.OPEN: 100,
            DoorState.VENTILATION_POSITION: 10,
            DoorState.POSITION_UNKNOWN: None,
        }
        return door_state_to_position.get(self.get_channel_or_raise().doorState)

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        channel = self.get_channel_or_raise()
        return channel.doorState == DoorState.CLOSED

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        channel = self.get_channel_or_raise()
        await channel.async_send_door_command(DoorCommand.OPEN)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        channel = self.get_channel_or_raise()
        await channel.async_send_door_command(DoorCommand.CLOSE)

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        channel = self.get_channel_or_raise()
        await channel.async_send_door_command(DoorCommand.STOP)


class HomematicipCoverShutterGroup(HomematicipGenericEntity, CoverEntity):
    """Representation of the HomematicIP cover shutter group."""

    _attr_has_entity_name = False
    _attr_device_class = CoverDeviceClass.SHUTTER

    def __init__(self, hap: HomematicipHAP, device, post: str = "ShutterGroup") -> None:
        """Initialize switching group."""
        device.modelType = f"HmIP-{post}"
        super().__init__(
            hap, device, post, is_multi_channel=False, feature_id="shutter"
        )

    @property
    @override
    def available(self) -> bool:
        """Cover shutter group available.

        A cover shutter group must be available, and should not be affected by
        the individual availability of group members.
        This allows controlling the shutters even when individual group
        members are not available.
        """
        return True

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self._device.shutterLevel is not None:
            return int((1 - self._device.shutterLevel) * 100)
        return None

    @property
    @override
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if self._device.slatsLevel is not None:
            return int((1 - self._device.slatsLevel) * 100)
        return None

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._device.shutterLevel is not None:
            return self._device.shutterLevel == HMIP_COVER_CLOSED
        return None

    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # HmIP cover is closed:1 -> open:0
        level = 1 - position / 100.0
        if level == HMIP_COVER_CLOSED:
            # Route fully-closed position through the same slats-safe call
            # as async_close_cover, otherwise slats get reset to 0 on FBL
            # group members. See issue #114266.
            await self.async_close_cover()
            return
        await self._device.set_shutter_level_async(level)

    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        # HmIP slats is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_slats_level_async(level)

    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover.

        The slats-safe call used in async_close_cover is intentionally not
        mirrored here: the regression reported in issue #114266 only
        affects close, and for an open cover slats at 0 (horizontal) is
        the natural rest position.
        """
        await self._device.set_shutter_level_async(HMIP_COVER_OPEN)

    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover.

        Use setSlatsLevel instead of setShutterLevel so HMIP Cloud does
        not reset slats to 0 (horizontal) on blind-capable group members
        (e.g. HmIP-FBL with firmware >= 1.10.16). See issue #114266.
        """
        await self._device.set_slats_level_async(
            slatsLevel=HMIP_SLATS_CLOSED, shutterLevel=HMIP_COVER_CLOSED
        )

    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the group if in motion."""
        await self._device.set_shutter_stop_async()

    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the slats."""
        await self._device.set_slats_level_async(HMIP_SLATS_OPEN)

    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the slats."""
        await self._device.set_slats_level_async(HMIP_SLATS_CLOSED)

    @override
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the group if in motion."""
        await self._device.set_shutter_stop_async()


COVER_CHANNEL_TYPES: tuple[
    tuple[tuple[FunctionalChannelType, ...], type[HomematicipChannelCover]], ...
] = (
    ((FunctionalChannelType.SHADING_CHANNEL,), HomematicipBlindModule),
    (
        (
            FunctionalChannelType.BLIND_CHANNEL,
            FunctionalChannelType.MULTI_MODE_INPUT_BLIND_CHANNEL,
        ),
        HomematicipMultiCoverSlats,
    ),
    ((FunctionalChannelType.SHUTTER_CHANNEL,), HomematicipMultiCoverShutter),
    ((FunctionalChannelType.DOOR_CHANNEL,), HomematicipGarageDoorModule),
)
