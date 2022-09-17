"""Support for Litter-Robot binary sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, cast

from pylitterbot import Robot

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity, _RobotT
from .hub import LitterRobotHub


class LitterRobotBinarySensorEntity(LitterRobotEntity[_RobotT], BinarySensorEntity):
    """Litter-Robot binary sensor entity."""

    entity_description: RobotBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return self.entity_description.is_on_fn(self.robot)


@dataclass
class RobotBinarySensorEntityDescriptionMixIn:
    """Value mixin for Litter-Robot binary sensors."""

    is_on_fn: Callable[[Robot], bool]


@dataclass
class RobotBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    RobotBinarySensorEntityDescriptionMixIn,
    Generic[_RobotT],
):
    """A class that describes robot binary sensor entities."""


BINARY_SENSOR_MAP: tuple[BinarySensorEntityDescription, ...] = (
    RobotBinarySensorEntityDescription(
        key="is_sleeping",
        name="Is sleeping",
        icon="mdi:sleep",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda robot: str(getattr(robot, "is_sleeping")) == "True",
    ),
    RobotBinarySensorEntityDescription(
        key="sleep_mode_enabled",
        name="Sleep mode enabled",
        icon="mdi:sleep",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda robot: cast(bool, getattr(robot, "sleep_mode_enabled")),
    ),
    RobotBinarySensorEntityDescription(
        key="power_status",
        name="Power status",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        is_on_fn=lambda robot: robot.power_status == "AC",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot binary sensors using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        LitterRobotBinarySensorEntity(robot=robot, hub=hub, description=description)
        for description in BINARY_SENSOR_MAP
        for robot in hub.account.robots
    )
