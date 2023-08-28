"""Base entity for Neato."""
from __future__ import annotations

from pybotvac import Robot

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import NEATO_DOMAIN


class NeatoEntity(Entity):
    """Base Neato entity."""

    _attr_has_entity_name = True

    def __init__(self, robot: Robot) -> None:
        """Initialize Neato entity."""
        self.robot = robot

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(NEATO_DOMAIN, self.robot.serial)},
            name=self.robot.name,
        )
