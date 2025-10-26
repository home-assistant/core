"""Support for Litter-Robot button."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot3, LitterRobot4, Robot

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _WhiskerEntityT


@dataclass(frozen=True, kw_only=True)
class RobotButtonEntityDescription(ButtonEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot button entities."""

    press_fn: Callable[[_WhiskerEntityT], Coroutine[Any, Any, bool]]


ROBOT_BUTTON_MAP: dict[type[Robot], RobotButtonEntityDescription] = {
    LitterRobot3: RobotButtonEntityDescription[LitterRobot3](
        key="reset_waste_drawer",
        translation_key="reset_waste_drawer",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda robot: robot.reset_waste_drawer(),
    ),
    LitterRobot4: RobotButtonEntityDescription[LitterRobot4](
        key="reset",
        translation_key="reset",
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda robot: robot.reset(),
    ),
    FeederRobot: RobotButtonEntityDescription[FeederRobot](
        key="give_snack",
        translation_key="give_snack",
        press_fn=lambda robot: robot.give_snack(),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LitterRobotButtonEntity(
            robot=robot, coordinator=coordinator, description=description
        )
        for robot in coordinator.account.robots
        for robot_type, description in ROBOT_BUTTON_MAP.items()
        if isinstance(robot, robot_type)
    )


class LitterRobotButtonEntity(LitterRobotEntity[_WhiskerEntityT], ButtonEntity):
    """Litter-Robot button entity."""

    entity_description: RobotButtonEntityDescription[_WhiskerEntityT]

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.robot)
        self.coordinator.async_set_updated_data(None)
