"""Support for Litter-Robot camera events."""

from __future__ import annotations

from typing import Any

from pylitterbot import LitterRobot5

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import LitterRobotEntity

# No actions performed by this entity.
PARALLEL_UPDATES = 0

ACTIVITY_TYPE_MAP: dict[str, str] = {
    "PET_VISIT": "pet_visit",
    "CAT_DETECT": "cat_detect",
    "MOTION": "motion",
    "CYCLE_COMPLETED": "cycle_completed",
    "CYCLE_INTERRUPTED": "cycle_interrupted",
    "LITTER_LOW": "litter_low",
    "OFFLINE": "offline",
}

EVENT_TYPES = list(ACTIVITY_TYPE_MAP.values())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot camera event entities using config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LitterRobotCameraEventEntity(robot=robot, coordinator=coordinator)
        for robot in coordinator.account.robots
        if isinstance(robot, LitterRobot5) and robot.has_camera
    )


class LitterRobotCameraEventEntity(LitterRobotEntity[LitterRobot5], EventEntity):
    """Event entity for Litter-Robot camera activity events."""

    _attr_device_class = EventDeviceClass.MOTION
    _attr_event_types = EVENT_TYPES
    _attr_translation_key = "camera_event"

    def __init__(
        self,
        robot: LitterRobot5,
        coordinator: LitterRobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the camera event entity."""
        super().__init__(
            robot,
            coordinator,
            EventEntityDescription(key="camera_event"),
        )
        self._last_activity_id: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        activities = self.coordinator.camera_activities.get(self.robot.serial, [])
        if not activities:
            super()._handle_coordinator_update()
            return

        latest = activities[0]
        activity_id = latest.get("messageId") or latest.get("id")
        if activity_id and activity_id != self._last_activity_id:
            self._last_activity_id = activity_id
            raw_type = latest.get("type", "")
            event_type = ACTIVITY_TYPE_MAP.get(raw_type, raw_type.lower())
            if event_type not in self._attr_event_types:
                event_type = "motion"

            attrs = self._build_event_attributes(latest)
            self._trigger_event(event_type, attrs)

        super()._handle_coordinator_update()

    def _build_event_attributes(self, activity: dict[str, Any]) -> dict[str, Any]:
        """Build event attributes from an activity dict."""
        attrs: dict[str, Any] = {}
        pet_ids = activity.get("petIds") or []
        if pet_ids:
            name_map = self.coordinator.pet_name_map
            pet_names = [name_map.get(pid, pid) for pid in pet_ids]
            attrs["pet_name"] = pet_names[0] if len(pet_names) == 1 else pet_names
        if (waste_type := activity.get("wasteType")) is not None:
            attrs["waste_type"] = waste_type
        if (waste_weight := activity.get("wasteWeight")) is not None:
            attrs["waste_weight_oz"] = round(waste_weight / 100 * 16, 1)
        if (duration := activity.get("duration")) is not None:
            attrs["duration"] = duration
        if (pet_weight := activity.get("petWeight")) is not None:
            attrs["pet_weight"] = round(pet_weight / 100, 1)
        return attrs
