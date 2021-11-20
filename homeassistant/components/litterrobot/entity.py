"""Litter-Robot entities for common data and methods."""
from __future__ import annotations

from datetime import time
import logging
from types import MethodType
from typing import Any

from pylitterbot import Robot
from pylitterbot.exceptions import InvalidCommandException

from homeassistant.const import ENTITY_CATEGORY_CONFIG
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .hub import LitterRobotHub

_LOGGER = logging.getLogger(__name__)

REFRESH_WAIT_TIME_SECONDS = 8


class LitterRobotEntity(CoordinatorEntity):
    """Generic Litter-Robot entity representing common data and methods."""

    def __init__(self, robot: Robot, entity_type: str, hub: LitterRobotHub) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(hub.coordinator)
        self.robot = robot
        self.entity_type = entity_type
        self.hub = hub

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return f"{self.robot.name} {self.entity_type}"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.robot.serial}-{self.entity_type}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device information for a Litter-Robot."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.robot.serial)},
            manufacturer="Litter-Robot",
            model=self.robot.model,
            name=self.robot.name,
        )


class LitterRobotControlEntity(LitterRobotEntity):
    """A Litter-Robot entity that can control the unit."""

    def __init__(self, robot: Robot, entity_type: str, hub: LitterRobotHub) -> None:
        """Init a Litter-Robot control entity."""
        super().__init__(robot=robot, entity_type=entity_type, hub=hub)
        self._refresh_callback = None

    async def perform_action_and_refresh(
        self, action: MethodType, *args: Any, **kwargs: Any
    ) -> bool:
        """Perform an action and initiates a refresh of the robot data after a few seconds."""
        success = False

        try:
            success = await action(*args, **kwargs)
        except InvalidCommandException as ex:  # pragma: no cover
            # this exception should only occur if the underlying API for commands changes
            _LOGGER.error(ex)
            success = False

        if success:
            self.async_cancel_refresh_callback()
            self._refresh_callback = async_call_later(
                self.hass, REFRESH_WAIT_TIME_SECONDS, self.async_call_later_callback
            )
        return success

    async def async_call_later_callback(self, *_) -> None:
        """Perform refresh request on callback."""
        self._refresh_callback = None
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel refresh callback when entity is being removed from hass."""
        self.async_cancel_refresh_callback()

    @callback
    def async_cancel_refresh_callback(self):
        """Clear the refresh callback if it has not already fired."""
        if self._refresh_callback is not None:
            self._refresh_callback()
            self._refresh_callback = None

    @staticmethod
    def parse_time_at_default_timezone(time_str: str) -> time | None:
        """Parse a time string and add default timezone."""
        if (parsed_time := dt_util.parse_time(time_str)) is None:
            return None

        return (
            dt_util.start_of_local_day()
            .replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
                second=parsed_time.second,
            )
            .timetz()
        )


class LitterRobotConfigEntity(LitterRobotControlEntity):
    """A Litter-Robot entity that can control configuration of the unit."""

    _attr_entity_category = ENTITY_CATEGORY_CONFIG

    def __init__(self, robot: Robot, entity_type: str, hub: LitterRobotHub) -> None:
        """Init a Litter-Robot control entity."""
        super().__init__(robot=robot, entity_type=entity_type, hub=hub)
        self._assumed_state: Any = None

    async def perform_action_and_assume_state(
        self, action: MethodType, assumed_state: Any
    ) -> bool:
        """Perform an action and assume the state passed in if call is successful."""
        if await self.perform_action_and_refresh(action, assumed_state):
            self._assumed_state = assumed_state
            self.async_write_ha_state()
