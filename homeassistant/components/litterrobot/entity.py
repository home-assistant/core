"""Litter-Robot entities for common data and methods."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate, Generic, TypeVar

from pylitterbot import Pet, Robot
from pylitterbot.exceptions import LitterRobotException
from pylitterbot.robot import EVENT_UPDATE

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LitterRobotDataUpdateCoordinator

_WhiskerEntityT = TypeVar("_WhiskerEntityT", bound=Robot | Pet)


def whisker_command[_WhiskerEntityT2: LitterRobotEntity, **_P](
    func: Callable[Concatenate[_WhiskerEntityT2, _P], Awaitable[None]],
) -> Callable[Concatenate[_WhiskerEntityT2, _P], Coroutine[Any, Any, None]]:
    """Wrap a Whisker command to handle exceptions."""

    async def handler(
        self: _WhiskerEntityT2, *args: _P.args, **kwargs: _P.kwargs
    ) -> None:
        try:
            await func(self, *args, **kwargs)
        except LitterRobotException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(ex)},
            ) from ex

    return handler


def get_device_info(whisker_entity: Robot | Pet) -> DeviceInfo:
    """Get device info for a robot or pet."""
    if isinstance(whisker_entity, Robot):
        return DeviceInfo(
            identifiers={(DOMAIN, whisker_entity.serial)},
            manufacturer="Whisker",
            model=whisker_entity.model,
            name=whisker_entity.name,
            serial_number=whisker_entity.serial,
            sw_version=getattr(whisker_entity, "firmware", None),
        )
    breed = ", ".join(breed for breed in whisker_entity.breeds or [])
    return DeviceInfo(
        identifiers={(DOMAIN, whisker_entity.id)},
        manufacturer="Whisker",
        model=f"{breed} {whisker_entity.pet_type}".strip().capitalize(),
        name=whisker_entity.name,
    )


class LitterRobotEntity(
    CoordinatorEntity[LitterRobotDataUpdateCoordinator], Generic[_WhiskerEntityT]
):
    """Generic Litter-Robot entity representing common data and methods."""

    _attr_has_entity_name = True

    def __init__(
        self,
        robot: _WhiskerEntityT,
        coordinator: LitterRobotDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.robot = robot
        self.entity_description = description
        _id = robot.serial if isinstance(robot, Robot) else robot.id
        self._attr_unique_id = f"{_id}-{description.key}"
        self._attr_device_info = get_device_info(robot)

    async def async_added_to_hass(self) -> None:
        """Set up a listener for the entity."""
        await super().async_added_to_hass()
        self.async_on_remove(self.robot.on(EVENT_UPDATE, self.async_write_ha_state))
