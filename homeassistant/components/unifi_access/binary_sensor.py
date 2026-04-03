"""Binary sensor platform for the UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import Door, DoorPositionStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator
from .entity import UnifiAccessEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Access binary sensor entities."""
    coordinator = entry.runtime_data
    added_doors: set[str] = set()

    @callback
    def _async_add_new_doors() -> None:
        new_door_ids = sorted(set(coordinator.data.doors) - added_doors)
        if not new_door_ids:
            return
        async_add_entities(
            UnifiAccessDoorPositionBinarySensor(
                coordinator, coordinator.data.doors[door_id]
            )
            for door_id in new_door_ids
        )
        added_doors.update(new_door_ids)

    _async_add_new_doors()
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_doors))


class UnifiAccessDoorPositionBinarySensor(UnifiAccessEntity, BinarySensorEntity):
    """Representation of a UniFi Access door position binary sensor."""

    _attr_name = None
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(coordinator, door, "access_door_dps")

    @property
    def is_on(self) -> bool:
        """Return whether the door is open."""
        return self._door.door_position_status == DoorPositionStatus.OPEN
