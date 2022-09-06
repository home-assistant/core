"""Litter-Robot entities for common data and methods."""
from __future__ import annotations

from collections.abc import Callable, Coroutine, Iterable
from datetime import time
import logging
from typing import Any, Generic, TypeVar

from pylitterbot import Robot
from pylitterbot.exceptions import InvalidCommandException
from typing_extensions import ParamSpec

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo, EntityCategory, EntityDescription
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .hub import LitterRobotHub

_P = ParamSpec("_P")
_RobotT = TypeVar("_RobotT", bound=Robot)
_LOGGER = logging.getLogger(__name__)

REFRESH_WAIT_TIME_SECONDS = 8


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
        # The following can be removed in 2022.12 after adjusting names in entities appropriately
        if description.name is not None:
            self._attr_name = description.name.capitalize()

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


class LitterRobotControlEntity(LitterRobotEntity[_RobotT]):
    """A Litter-Robot entity that can control the unit."""

    def __init__(
        self, robot: _RobotT, hub: LitterRobotHub, description: EntityDescription
    ) -> None:
        """Init a Litter-Robot control entity."""
        super().__init__(robot=robot, hub=hub, description=description)
        self._refresh_callback: CALLBACK_TYPE | None = None

    async def perform_action_and_refresh(
        self,
        action: Callable[_P, Coroutine[Any, Any, bool]],
        *args: _P.args,
        **kwargs: _P.kwargs,
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

    async def async_call_later_callback(self, *_: Any) -> None:
        """Perform refresh request on callback."""
        self._refresh_callback = None
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel refresh callback when entity is being removed from hass."""
        self.async_cancel_refresh_callback()

    @callback
    def async_cancel_refresh_callback(self) -> None:
        """Clear the refresh callback if it has not already fired."""
        if self._refresh_callback is not None:
            self._refresh_callback()
            self._refresh_callback = None

    @staticmethod
    def parse_time_at_default_timezone(time_str: str | None) -> time | None:
        """Parse a time string and add default timezone."""
        if time_str is None:
            return None

        if (parsed_time := dt_util.parse_time(time_str)) is None:  # pragma: no cover
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


class LitterRobotConfigEntity(LitterRobotControlEntity[_RobotT]):
    """A Litter-Robot entity that can control configuration of the unit."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, robot: _RobotT, hub: LitterRobotHub, description: EntityDescription
    ) -> None:
        """Init a Litter-Robot control entity."""
        super().__init__(robot=robot, hub=hub, description=description)
        self._assumed_state: bool | None = None

    async def perform_action_and_assume_state(
        self, action: Callable[[bool], Coroutine[Any, Any, bool]], assumed_state: bool
    ) -> None:
        """Perform an action and assume the state passed in if call is successful."""
        if await self.perform_action_and_refresh(action, assumed_state):
            self._assumed_state = assumed_state
            self.async_write_ha_state()


def async_update_unique_id(
    hass: HomeAssistant, domain: str, entities: Iterable[LitterRobotEntity[_RobotT]]
) -> None:
    """Update unique ID to be based on entity description key instead of name.

    Introduced with release 2022.9.
    """
    ent_reg = er.async_get(hass)
    for entity in entities:
        old_unique_id = f"{entity.robot.serial}-{entity.entity_description.name}"
        if entity_id := ent_reg.async_get_entity_id(domain, DOMAIN, old_unique_id):
            new_unique_id = f"{entity.robot.serial}-{entity.entity_description.key}"
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)
