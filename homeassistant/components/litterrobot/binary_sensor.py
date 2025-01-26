"""Support for Litter-Robot binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from pylitterbot import LitterRobot, Robot

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _RobotT


@dataclass(frozen=True, kw_only=True)
class RobotBinarySensorEntityDescription(
    BinarySensorEntityDescription, Generic[_RobotT]
):
    """A class that describes robot binary sensor entities."""

    is_on_fn: Callable[[_RobotT], bool]


BINARY_SENSOR_MAP: dict[type[Robot], tuple[RobotBinarySensorEntityDescription, ...]] = {
    LitterRobot: (  # type: ignore[type-abstract]  # only used for isinstance check
        RobotBinarySensorEntityDescription[LitterRobot](
            key="sleeping",
            translation_key="sleeping",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            is_on_fn=lambda robot: robot.is_sleeping,
        ),
        RobotBinarySensorEntityDescription[LitterRobot](
            key="sleep_mode",
            translation_key="sleep_mode",
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            is_on_fn=lambda robot: robot.sleep_mode_enabled,
        ),
    ),
    Robot: (  # type: ignore[type-abstract]  # only used for isinstance check
        RobotBinarySensorEntityDescription[Robot](
            key="power_status",
            translation_key="power_status",
            device_class=BinarySensorDeviceClass.PLUG,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            is_on_fn=lambda robot: robot.power_status == "AC",
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot binary sensors using config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LitterRobotBinarySensorEntity(
            robot=robot, coordinator=coordinator, description=description
        )
        for robot in coordinator.account.robots
        for robot_type, entity_descriptions in BINARY_SENSOR_MAP.items()
        if isinstance(robot, robot_type)
        for description in entity_descriptions
    )


class LitterRobotBinarySensorEntity(LitterRobotEntity[_RobotT], BinarySensorEntity):
    """Litter-Robot binary sensor entity."""

    entity_description: RobotBinarySensorEntityDescription[_RobotT]

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self.entity_description.is_on_fn(self.robot)
