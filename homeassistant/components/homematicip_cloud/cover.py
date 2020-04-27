"""Support for HomematicIP Cloud cover devices."""
import logging
from typing import Optional

from homematicip.aio.device import (
    AsyncFullFlushBlind,
    AsyncFullFlushShutter,
    AsyncGarageDoorModuleTormatic,
)
from homematicip.aio.group import AsyncExtendedLinkedShutterGroup
from homematicip.base.enums import DoorCommand, DoorState

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

from . import DOMAIN as HMIPC_DOMAIN, HomematicipGenericDevice
from .hap import HomematicipHAP

_LOGGER = logging.getLogger(__name__)

HMIP_COVER_OPEN = 0
HMIP_COVER_CLOSED = 1
HMIP_SLATS_OPEN = 0
HMIP_SLATS_CLOSED = 1


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the HomematicIP cover from a config entry."""
    hap = hass.data[HMIPC_DOMAIN][config_entry.unique_id]
    entities = []
    for device in hap.home.devices:
        if isinstance(device, AsyncFullFlushBlind):
            entities.append(HomematicipCoverSlats(hap, device))
        elif isinstance(device, AsyncFullFlushShutter):
            entities.append(HomematicipCoverShutter(hap, device))
        elif isinstance(device, AsyncGarageDoorModuleTormatic):
            entities.append(HomematicipGarageDoorModuleTormatic(hap, device))

    for group in hap.home.groups:
        if isinstance(group, AsyncExtendedLinkedShutterGroup):
            entities.append(HomematicipCoverShutterGroup(hap, group))

    if entities:
        async_add_entities(entities)


class HomematicipCoverShutter(HomematicipGenericDevice, CoverEntity):
    """Representation of a HomematicIP Cloud cover shutter device."""

    @property
    def current_cover_position(self) -> int:
        """Return current position of cover."""
        if self._device.shutterLevel is not None:
            return int((1 - self._device.shutterLevel) * 100)
        return None

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        # HmIP cover is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_shutter_level(level)

    @property
    def is_closed(self) -> Optional[bool]:
        """Return if the cover is closed."""
        if self._device.shutterLevel is not None:
            return self._device.shutterLevel == HMIP_COVER_CLOSED
        return None

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        await self._device.set_shutter_level(HMIP_COVER_OPEN)

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover."""
        await self._device.set_shutter_level(HMIP_COVER_CLOSED)

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the device if in motion."""
        await self._device.set_shutter_stop()


class HomematicipCoverSlats(HomematicipCoverShutter, CoverEntity):
    """Representation of a HomematicIP Cloud cover slats device."""

    @property
    def current_cover_tilt_position(self) -> int:
        """Return current tilt position of cover."""
        if self._device.slatsLevel is not None:
            return int((1 - self._device.slatsLevel) * 100)
        return None

    async def async_set_cover_tilt_position(self, **kwargs) -> None:
        """Move the cover to a specific tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        # HmIP slats is closed:1 -> open:0
        level = 1 - position / 100.0
        await self._device.set_slats_level(level)

    async def async_open_cover_tilt(self, **kwargs) -> None:
        """Open the slats."""
        await self._device.set_slats_level(HMIP_SLATS_OPEN)

    async def async_close_cover_tilt(self, **kwargs) -> None:
        """Close the slats."""
        await self._device.set_slats_level(HMIP_SLATS_CLOSED)

    async def async_stop_cover_tilt(self, **kwargs) -> None:
        """Stop the device if in motion."""
        await self._device.set_shutter_stop()


class HomematicipGarageDoorModuleTormatic(HomematicipGenericDevice, CoverEntity):
    """Representation of a HomematicIP Garage Door Module for Tormatic."""

    @property
    def current_cover_position(self) -> int:
        """Return current position of cover."""
        door_state_to_position = {
            DoorState.CLOSED: 0,
            DoorState.OPEN: 100,
            DoorState.VENTILATION_POSITION: 10,
            DoorState.POSITION_UNKNOWN: None,
        }
        return door_state_to_position.get(self._device.doorState)

    @property
    def is_closed(self) -> Optional[bool]:
        """Return if the cover is closed."""
        return self._device.doorState == DoorState.CLOSED

    async def async_open_cover(self, **kwargs) -> None:
        """Open the cover."""
        await self._device.send_door_command(DoorCommand.OPEN)

    async def async_close_cover(self, **kwargs) -> None:
        """Close the cover."""
        await self._device.send_door_command(DoorCommand.CLOSE)

    async def async_stop_cover(self, **kwargs) -> None:
        """Stop the cover."""
        await self._device.send_door_command(DoorCommand.STOP)


class HomematicipCoverShutterGroup(HomematicipCoverSlats, CoverEntity):
    """Representation of a HomematicIP Cloud cover shutter group."""

    def __init__(self, hap: HomematicipHAP, device, post: str = "ShutterGroup") -> None:
        """Initialize switching group."""
        device.modelType = f"HmIP-{post}"
        super().__init__(hap, device, post)
