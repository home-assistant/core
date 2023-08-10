"""Support for Litter-Robot updates."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from pylitterbot import LitterRobot4

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity, LitterRobotHub

SCAN_INTERVAL = timedelta(days=1)

FIRMWARE_UPDATE_ENTITY = UpdateEntityDescription(
    key="firmware",
    translation_key="firmware",
    device_class=UpdateDeviceClass.FIRMWARE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot update platform."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    entities = [
        RobotUpdateEntity(robot=robot, hub=hub, description=FIRMWARE_UPDATE_ENTITY)
        for robot in hub.litter_robots()
        if isinstance(robot, LitterRobot4)
    ]
    async_add_entities(entities, True)


class RobotUpdateEntity(LitterRobotEntity[LitterRobot4], UpdateEntity):
    """A class that describes robot update entities."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    @property
    def installed_version(self) -> str:
        """Version installed and in use."""
        return self.robot.firmware

    @property
    def in_progress(self) -> bool:
        """Update installation progress."""
        return self.robot.firmware_update_triggered

    @property
    def should_poll(self) -> bool:
        """Set polling to True."""
        return True

    async def async_update(self) -> None:
        """Update the entity."""
        # If the robot has a firmware update already in progress, checking for the
        # latest firmware informs that an update has already been triggered, no
        # firmware information is returned and we won't know the latest version.
        if not self.robot.firmware_update_triggered:
            latest_version = await self.robot.get_latest_firmware(True)
            if not await self.robot.has_firmware_update():
                latest_version = self.robot.firmware
            self._attr_latest_version = latest_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if await self.robot.has_firmware_update(True):
            if not await self.robot.update_firmware():
                message = f"Unable to start firmware update on {self.robot.name}"
                raise HomeAssistantError(message)
