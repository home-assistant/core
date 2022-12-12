"""Support for Litter-Robot updates."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
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
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_start

from .const import DOMAIN
from .entity import LitterRobotEntity, LitterRobotHub

FIRMWARE_UPDATE_ENTITY = UpdateEntityDescription(
    key="firmware",
    name="Firmware",
    device_class=UpdateDeviceClass.FIRMWARE,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot update platform."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    robots = hub.account.robots
    entities = [
        RobotUpdateEntity(robot=robot, hub=hub, description=FIRMWARE_UPDATE_ENTITY)
        for robot in robots
        if isinstance(robot, LitterRobot4)
    ]
    async_add_entities(entities)


class RobotUpdateEntity(LitterRobotEntity[LitterRobot4], UpdateEntity):
    """A class that describes robot update entities."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(
        self,
        robot: LitterRobot4,
        hub: LitterRobotHub,
        description: UpdateEntityDescription,
    ) -> None:
        """Initialize a Litter-Robot update entity."""
        super().__init__(robot, hub, description)
        self._poll_unsub: Callable[[], None] | None = None

    @property
    def installed_version(self) -> str:
        """Version installed and in use."""
        return self.robot.firmware

    @property
    def in_progress(self) -> bool:
        """Update installation progress."""
        return self.robot.firmware_update_triggered

    async def _async_update(self, _: HomeAssistant | datetime | None = None) -> None:
        """Update the entity."""
        self._poll_unsub = None

        if await self.robot.has_firmware_update():
            latest_version = await self.robot.get_latest_firmware()
        else:
            latest_version = self.installed_version

        if self._attr_latest_version != self.installed_version:
            self._attr_latest_version = latest_version
            self.async_write_ha_state()

        self._poll_unsub = async_call_later(
            self.hass, timedelta(days=1), self._async_update
        )

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(async_at_start(self.hass, self._async_update))

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        if await self.robot.has_firmware_update():
            if not await self.robot.update_firmware():
                message = f"Unable to start firmware update on {self.robot.name}"
                raise HomeAssistantError(message)

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed."""
        if self._poll_unsub:
            self._poll_unsub()
            self._poll_unsub = None
