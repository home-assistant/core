"""Litter-Robot entities for common data and methods."""
from __future__ import annotations

from typing import Generic, TypeVar

from pylitterbot import Robot
from pylitterbot.robot import EVENT_UPDATE

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .hub import LitterRobotHub

_RobotT = TypeVar("_RobotT", bound=Robot)


class LitterRobotEntity(
    CoordinatorEntity[DataUpdateCoordinator[bool]], Generic[_RobotT]
):
    """Generic Litter-Robot entity representing common data and methods."""

    _attr_has_entity_name = True

    def __init__(
        self, robot: _RobotT, hub: LitterRobotHub, description: EntityDescription
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(hub.coordinator)
        self.robot = robot
        self.hub = hub
        self.entity_description = description
        self._attr_unique_id = f"{self.robot.serial}-{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information for a Litter-Robot."""
        assert self.robot.serial
        return DeviceInfo(
            identifiers={(DOMAIN, self.robot.serial)},
            manufacturer="Litter-Robot",
            model=self.robot.model,
            name=self.robot.name,
            sw_version=getattr(self.robot, "firmware", None),
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self.robot.on(EVENT_UPDATE, self.async_write_ha_state))
