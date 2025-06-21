"""Support for HomematicIP Cloud cover devices."""

from __future__ import annotations

from typing import Any

from homematicip.base.enums import DoorCommand, DoorState
from homematicip.device import (
    BlindModule,
    DinRailBlind4,
    FullFlushBlind,
    FullFlushShutter,
    GarageDoorModuleTormatic,
    HoermannDrivesModule,
)
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
        if isinstance(device, BlindModule):
            entities.append(HomematicipBlindModule(hap, device))
        elif isinstance(device, DinRailBlind4):
            entities.extend(
                HomematicipMultiCoverSlats(hap, device, channel=channel)
                for channel in range(1, 5)
            )
        elif isinstance(device, FullFlushBlind):
            entities.append(HomematicipCoverSlats(hap, device))
        elif isinstance(device, FullFlushShutter):
            entities.append(HomematicipCoverShutter(hap, device))
        elif isinstance(device, (HoermannDrivesModule, GarageDoorModuleTormatic)):
            entities.append(HomematicipGarageDoorModule(hap, device))

    async_add_entities(entities)


class HomematicipBlindModule(HomematicipGenericEntity, CoverEntity):
    """Representation of the HomematicIP blind module."""

    _attr_device_class = CoverDeviceClass.BLIND

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self._device.primaryShadingLevel is not None:
            return int((1 - self._device.primaryShadingLevel) * 100)
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if self._device.secondaryShadingLevel is not None:
            return int((1 - self._device.secondaryShadingLevel) * 100)
        return None

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # HmIP cover is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_primary_shading_level_async(primaryShadingLevel=level)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        # HmIP slats is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_secondary_shading_level_async(
            primaryShadingLevel=self._device.primaryShadingLevel,
            secondaryShadingLevel=level,
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._device.primaryShadingLevel is not None:
            return self._device.primaryShadingLevel == HMIP_COVER_CLOSED
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.set_primary_shading_level_async(
            primaryShadingLevel=HMIP_COVER_OPEN
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._device.set_primary_shading_level_async(
            primaryShadingLevel=HMIP_COVER_CLOSED
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        await self._device.stop_async()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the slats."""
        await self._device.set_secondary_shading_level_async(
            primaryShadingLevel=self._device.primaryShadingLevel,
            secondaryShadingLevel=HMIP_SLATS_OPEN,
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the slats."""
        await self._device.set_secondary_shading_level_async(
            primaryShadingLevel=self._device.primaryShadingLevel,
            secondaryShadingLevel=HMIP_SLATS_CLOSED,
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        await self._device.stop_async()


class HomematicipMultiCoverShutter(HomematicipGenericEntity, CoverEntity):
    """Representation of the HomematicIP cover shutter."""

    _attr_device_class = CoverDeviceClass.SHUTTER

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        channel=1,
        is_multi_channel=True,
    ) -> None:
        """Initialize the multi cover entity."""
        super().__init__(
            hap, device, channel=channel, is_multi_channel=is_multi_channel
        )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self._device.functionalChannels[self._channel].shutterLevel is not None:
            return int(
                (1 - self._device.functionalChannels[self._channel].shutterLevel) * 100
            )
        return None

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # HmIP cover is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_shutter_level_async(level, self._channel)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._device.functionalChannels[self._channel].shutterLevel is not None:
            return (
                self._device.functionalChannels[self._channel].shutterLevel
                == HMIP_COVER_CLOSED
            )
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.set_shutter_level_async(HMIP_COVER_OPEN, self._channel)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._device.set_shutter_level_async(HMIP_COVER_CLOSED, self._channel)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        await self._device.set_shutter_stop_async(self._channel)


class HomematicipCoverShutter(HomematicipMultiCoverShutter, CoverEntity):
    """Representation of the HomematicIP cover shutter."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the multi cover entity."""
        super().__init__(hap, device, is_multi_channel=False)


class HomematicipMultiCoverSlats(HomematicipMultiCoverShutter, CoverEntity):
    """Representation of the HomematicIP multi cover slats."""

    def __init__(
        self,
        hap: HomematicipHAP,
        device,
        channel=1,
        is_multi_channel=True,
    ) -> None:
        """Initialize the multi slats entity."""
        super().__init__(
            hap, device, channel=channel, is_multi_channel=is_multi_channel
        )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if self._device.functionalChannels[self._channel].slatsLevel is not None:
            return int(
                (1 - self._device.functionalChannels[self._channel].slatsLevel) * 100
            )
        return None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        # HmIP slats is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_slats_level_async(
            slatsLevel=level, channelIndex=self._channel
        )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the slats."""
        await self._device.set_slats_level_async(
            slatsLevel=HMIP_SLATS_OPEN, channelIndex=self._channel
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the slats."""
        await self._device.set_slats_level_async(
            slatsLevel=HMIP_SLATS_CLOSED, channelIndex=self._channel
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the device if in motion."""
        await self._device.set_shutter_stop_async(self._channel)


class HomematicipCoverSlats(HomematicipMultiCoverSlats, CoverEntity):
    """Representation of the HomematicIP cover slats."""

    def __init__(self, hap: HomematicipHAP, device) -> None:
        """Initialize the multi slats entity."""
        super().__init__(hap, device, is_multi_channel=False)


class HomematicipGarageDoorModule(HomematicipGenericEntity, CoverEntity):
    """Representation of the HomematicIP Garage Door Module."""

    _attr_device_class = CoverDeviceClass.GARAGE

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        door_state_to_position = {
            DoorState.CLOSED: 0,
            DoorState.OPEN: 100,
            DoorState.VENTILATION_POSITION: 10,
            DoorState.POSITION_UNKNOWN: None,
        }
        return door_state_to_position.get(self._device.doorState)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._device.doorState == DoorState.CLOSED

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.send_door_command_async(DoorCommand.OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._device.send_door_command_async(DoorCommand.CLOSE)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._device.send_door_command_async(DoorCommand.STOP)


class HomematicipCoverShutterGroup(HomematicipGenericEntity, CoverEntity):
    """Representation of the HomematicIP cover shutter group."""

    _attr_device_class = CoverDeviceClass.SHUTTER

    def __init__(self, hap: HomematicipHAP, device, post: str = "ShutterGroup") -> None:
        """Initialize switching group."""
        device.modelType = f"HmIP-{post}"
        super().__init__(hap, device, post, is_multi_channel=False)

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self._device.shutterLevel is not None:
            return int((1 - self._device.shutterLevel) * 100)
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if self._device.slatsLevel is not None:
            return int((1 - self._device.slatsLevel) * 100)
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._device.shutterLevel is not None:
            return self._device.shutterLevel == HMIP_COVER_CLOSED
        return None

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # HmIP cover is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_shutter_level_async(level)

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        # HmIP slats is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_slats_level_async(level)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._device.set_shutter_level_async(HMIP_COVER_OPEN)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._device.set_shutter_level_async(HMIP_COVER_CLOSED)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the group if in motion."""
        await self._device.set_shutter_stop_async()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the slats."""
        await self._device.set_slats_level_async(HMIP_SLATS_OPEN)

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the slats."""
        await self._device.set_slats_level_async(HMIP_SLATS_CLOSED)

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the group if in motion."""
        await self._device.set_shutter_stop_async()
