"""Support for Litter-Robot button."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, Generic

from pylitterbot import (
    FeederRobot,
    LitterRobot3,
    LitterRobot4,
    LitterRobot5,
    Pet,
    Robot,
)
from pylitterbot.exceptions import LitterRobotException

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import LitterRobotEntity, _WhiskerEntityT, get_device_info, whisker_command

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RobotButtonEntityDescription(ButtonEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot button entities."""

    press_fn: Callable[[_WhiskerEntityT], Coroutine[Any, Any, bool]]


ROBOT_BUTTON_MAP: dict[tuple[type[Robot], ...], RobotButtonEntityDescription] = {
    (LitterRobot3, LitterRobot5): RobotButtonEntityDescription[
        LitterRobot3 | LitterRobot5
    ](
        key="reset_waste_drawer",
        translation_key="reset_waste_drawer",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda robot: robot.reset_waste_drawer(),
    ),
    (LitterRobot4, LitterRobot5): RobotButtonEntityDescription[
        LitterRobot4 | LitterRobot5
    ](
        key="reset",
        translation_key="reset",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda robot: robot.reset(),
    ),
    (LitterRobot5,): RobotButtonEntityDescription[LitterRobot5](
        key="change_filter",
        translation_key="change_filter",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda robot: robot.change_filter(),
    ),
    (FeederRobot,): RobotButtonEntityDescription[FeederRobot](
        key="give_snack",
        translation_key="give_snack",
        press_fn=lambda robot: robot.give_snack(),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = [
        LitterRobotButtonEntity(
            robot=robot, coordinator=coordinator, description=description
        )
        for robot in coordinator.account.robots
        for robot_type, description in ROBOT_BUTTON_MAP.items()
        if isinstance(robot, robot_type)
    ]

    pets = list(coordinator.account.pets)
    for pet in pets:
        others = [p for p in pets if p.id != pet.id]
        entities.extend(
            ReassignVisitButton(pet, other, coordinator) for other in others
        )
        entities.append(UnassignVisitButton(pet, coordinator))

    async_add_entities(entities)


class LitterRobotButtonEntity(LitterRobotEntity[_WhiskerEntityT], ButtonEntity):
    """Litter-Robot button entity."""

    entity_description: RobotButtonEntityDescription[_WhiskerEntityT]

    @whisker_command
    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.robot)
        self.coordinator.async_set_updated_data(None)


class ReassignVisitButton(ButtonEntity):
    """Button to reassign a pet's latest visit to another pet."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:swap-horizontal"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "reassign_visit"

    def __init__(
        self,
        from_pet: Pet,
        to_pet: Pet,
        coordinator: LitterRobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the reassign visit button."""
        self._from_pet = from_pet
        self._to_pet = to_pet
        self.coordinator = coordinator
        slug = to_pet.name.lower().replace(" ", "_")
        self._attr_unique_id = f"{from_pet.id}-reassign_visit_to_{slug}"
        self._attr_translation_placeholders = {"pet_name": to_pet.name}
        self._attr_device_info = get_device_info(from_pet)

    async def async_press(self) -> None:
        """Reassign the from_pet's latest visit to to_pet."""
        activity = self._find_latest_visit()
        if activity is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_recent_visit",
                translation_placeholders={"name": self._from_pet.name},
            )

        event_id = activity.get("eventId")
        if not event_id:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="visit_no_event_id",
            )

        robot = self._find_robot(activity)
        if robot is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="robot_not_found",
            )

        try:
            result = await robot.reassign_pet_visit(
                event_id=event_id,
                from_pet_id=self._from_pet.id,
                to_pet_id=self._to_pet.id,
            )
        except LitterRobotException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex

        if result is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reassign_failed",
            )

        self._update_cache(activity, result)
        self.coordinator.async_set_updated_data(None)

    def _find_latest_visit(self) -> dict[str, Any] | None:
        """Find the latest visit for from_pet in the activity cache."""
        for activities in self.coordinator.camera_activities.values():
            for activity in activities:
                pet_ids = activity.get("petIds") or []
                pet_id = activity.get("petId")
                if self._from_pet.id in pet_ids or self._from_pet.id == pet_id:
                    return activity
        return None

    def _find_robot(self, activity: dict[str, Any]) -> LitterRobot5 | None:
        """Find the LR5 robot that owns this activity."""
        for serial, activities in self.coordinator.camera_activities.items():
            if activity in activities:
                for robot in self.coordinator.account.robots:
                    if isinstance(robot, LitterRobot5) and robot.serial == serial:
                        return robot
        return None

    def _update_cache(self, old: dict[str, Any], new: dict[str, Any]) -> None:
        """Replace the old activity with the new one in the cache."""
        for serial, activities in self.coordinator.camera_activities.items():
            for i, act in enumerate(activities):
                if act is old:
                    self.coordinator.camera_activities[serial][i] = new
                    return


class UnassignVisitButton(ButtonEntity):
    """Button to unassign a pet's latest visit."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:close-circle-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "unassign_visit"

    def __init__(
        self,
        pet: Pet,
        coordinator: LitterRobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the unassign visit button."""
        self._pet = pet
        self.coordinator = coordinator
        self._attr_unique_id = f"{pet.id}-unassign_visit"
        self._attr_device_info = get_device_info(pet)

    async def async_press(self) -> None:
        """Unassign the pet's latest visit."""
        activity = self._find_latest_visit()
        if activity is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_recent_visit",
                translation_placeholders={"name": self._pet.name},
            )

        event_id = activity.get("eventId")
        if not event_id:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="visit_no_event_id",
            )

        robot = self._find_robot(activity)
        if robot is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="robot_not_found",
            )

        try:
            result = await robot.reassign_pet_visit(
                event_id=event_id,
                from_pet_id=self._pet.id,
                to_pet_id=None,
            )
        except LitterRobotException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex

        if result is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reassign_failed",
            )

        self._update_cache(activity, result)
        self.coordinator.async_set_updated_data(None)

    def _find_latest_visit(self) -> dict[str, Any] | None:
        """Find the latest visit for this pet in the activity cache."""
        for activities in self.coordinator.camera_activities.values():
            for activity in activities:
                pet_ids = activity.get("petIds") or []
                pet_id = activity.get("petId")
                if self._pet.id in pet_ids or self._pet.id == pet_id:
                    return activity
        return None

    def _find_robot(self, activity: dict[str, Any]) -> LitterRobot5 | None:
        """Find the LR5 robot that owns this activity."""
        for serial, activities in self.coordinator.camera_activities.items():
            if activity in activities:
                for robot in self.coordinator.account.robots:
                    if isinstance(robot, LitterRobot5) and robot.serial == serial:
                        return robot
        return None

    def _update_cache(self, old: dict[str, Any], new: dict[str, Any]) -> None:
        """Replace the old activity with the new one in the cache."""
        for serial, activities in self.coordinator.camera_activities.items():
            for i, act in enumerate(activities):
                if act is old:
                    self.coordinator.camera_activities[serial][i] = new
                    return
