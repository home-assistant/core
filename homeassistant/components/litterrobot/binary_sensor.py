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
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity, _RobotT
from .hub import LitterRobotHub


@dataclass(frozen=True)
class RequiredKeysMixin(Generic[_RobotT]):
    """A class that describes robot binary sensor entity required keys."""

    is_on_fn: Callable[[_RobotT], bool]


@dataclass(frozen=True)
class RobotBinarySensorEntityDescription(
    BinarySensorEntityDescription, RequiredKeysMixin[_RobotT]
):
    """A class that describes robot binary sensor entities."""


class LitterRobotBinarySensorEntity(LitterRobotEntity[_RobotT], BinarySensorEntity):
    """Litter-Robot binary sensor entity."""

    entity_description: RobotBinarySensorEntityDescription[_RobotT]

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self.entity_description.is_on_fn(self.robot)


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
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot binary sensors using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LitterRobotBinarySensorEntity(robot=robot, hub=hub, description=description)
        for robot in hub.account.robots
        for robot_type, entity_descriptions in BINARY_SENSOR_MAP.items()
        if isinstance(robot, robot_type)
        for description in entity_descriptions
    )
