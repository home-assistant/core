"""Support for Honeywell Lyric select platform."""

from __future__ import annotations

import logging

from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
from aiolyric.objects.priority import LyricRoom

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LYRIC_EXCEPTIONS
from .coordinator import LyricConfigEntry, LyricDataUpdateCoordinator
from .entity import LyricDeviceEntity

_LOGGER = logging.getLogger(__name__)

# Honeywell Lyric API priority types
PRIORITY_TYPE_PICK_A_ROOM = "PickARoom"
PRIORITY_TYPE_FOLLOW_ME = "FollowMe"
PRIORITY_TYPE_WHOLE_HOUSE = "WholeHouse"

# Option shown in the select for the FollowMe mode
OPTION_FOLLOW_ME = "follow_me"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LyricConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Honeywell Lyric select entities based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        LyricRoomPrioritySelect(coordinator, location, device)
        for location in coordinator.data.locations
        for device in location.devices
        if device.device_class == "Thermostat"
        and device.device_id.startswith("LCC")
        and coordinator.data.rooms_dict.get(device.mac_id)
    )


class LyricRoomPrioritySelect(LyricDeviceEntity, SelectEntity):
    """Select entity for Honeywell Lyric thermostat room priority."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "room_priority"

    def __init__(
        self,
        coordinator: LyricDataUpdateCoordinator,
        location: LyricLocation,
        device: LyricDevice,
    ) -> None:
        """Initialize the room priority select entity."""
        super().__init__(
            coordinator,
            location,
            device,
            f"{device.mac_id}_room_priority",
        )

    @property
    def _rooms(self) -> dict[int, LyricRoom]:
        """Return the rooms for this thermostat."""
        return self.coordinator.data.rooms_dict.get(self._mac_id, {})

    @property
    def options(self) -> list[str]:
        """Return the list of available room priority options."""
        room_options = sorted(
            room.room_name for room in self._rooms.values() if room.room_name
        )
        return [OPTION_FOLLOW_ME, *room_options]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected room priority."""
        priority = self.coordinator.data.priorities_dict.get(self._mac_id)
        if priority is None:
            return None

        current = priority.current_priority
        if current.priority_type == PRIORITY_TYPE_FOLLOW_ME:
            return OPTION_FOLLOW_ME

        if current.priority_type == PRIORITY_TYPE_PICK_A_ROOM:
            selected = current.selected_rooms
            if selected:
                room = self._rooms.get(selected[0])
                if room is not None:
                    return room.room_name

        return None

    async def async_select_option(self, option: str) -> None:
        """Set the room priority."""
        if option == OPTION_FOLLOW_ME:
            priority_type = PRIORITY_TYPE_FOLLOW_ME
            rooms: list[int] = []
        else:
            priority_type = PRIORITY_TYPE_PICK_A_ROOM
            room_id = next(
                (
                    rid
                    for rid, room in self._rooms.items()
                    if room.room_name == option
                ),
                None,
            )
            if room_id is None:
                _LOGGER.error("Room not found: %s", option)
                return
            rooms = [room_id]

        _LOGGER.debug(
            "Set room priority: type=%s, rooms=%s", priority_type, rooms
        )
        try:
            await self.coordinator.data.update_priority(
                self.location,
                self.device,
                priority_type=priority_type,
                rooms=rooms,
            )
        except LYRIC_EXCEPTIONS as exception:
            _LOGGER.error(exception)
        await self.coordinator.async_refresh()
