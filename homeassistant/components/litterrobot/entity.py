"""Litter-Robot entities for common data and methods."""

from __future__ import annotations

from typing import Generic, TypeVar

from pylitterbot import Robot
from pylitterbot.robot import EVENT_UPDATE

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LitterRobotDataUpdateCoordinator

_RobotT = TypeVar("_RobotT", bound=Robot)


class LitterRobotEntity(
    CoordinatorEntity[LitterRobotDataUpdateCoordinator], Generic[_RobotT]
):
    """Generic Litter-Robot entity representing common data and methods."""

    _attr_has_entity_name = True

    def __init__(
        self,
        robot: _RobotT,
        coordinator: LitterRobotDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.robot = robot
        self.entity_description = description
        self._attr_unique_id = f"{robot.serial}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, robot.serial)},
            manufacturer="Whisker",
            model=robot.model,
            name=robot.name,
            serial_number=robot.serial,
            sw_version=getattr(robot, "firmware", None),
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self.robot.on(EVENT_UPDATE, self.async_write_ha_state))
