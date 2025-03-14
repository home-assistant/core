"""Support for Litter-Robot selects."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4, Robot
from pylitterbot.robot.litterrobot4 import BrightnessLevel

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import LitterRobotEntity, _WhiskerEntityT

_CastTypeT = TypeVar("_CastTypeT", int, float, str)


@dataclass(frozen=True, kw_only=True)
class RobotSelectEntityDescription(
    SelectEntityDescription, Generic[_WhiskerEntityT, _CastTypeT]
):
    """A class that describes robot select entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG
    current_fn: Callable[[_WhiskerEntityT], _CastTypeT | None]
    options_fn: Callable[[_WhiskerEntityT], list[_CastTypeT]]
    select_fn: Callable[[_WhiskerEntityT, str], Coroutine[Any, Any, bool]]


ROBOT_SELECT_MAP: dict[type[Robot], RobotSelectEntityDescription] = {
    LitterRobot: RobotSelectEntityDescription[LitterRobot, int](  # type: ignore[type-abstract]  # only used for isinstance check
        key="cycle_delay",
        translation_key="cycle_delay",
        unit_of_measurement=UnitOfTime.MINUTES,
        current_fn=lambda robot: robot.clean_cycle_wait_time_minutes,
        options_fn=lambda robot: robot.VALID_WAIT_TIMES,
        select_fn=lambda robot, opt: robot.set_wait_time(int(opt)),
    ),
    LitterRobot4: RobotSelectEntityDescription[LitterRobot4, str](
        key="panel_brightness",
        translation_key="brightness_level",
        current_fn=(
            lambda robot: bri.name.lower()
            if (bri := robot.panel_brightness) is not None
            else None
        ),
        options_fn=lambda _: [level.name.lower() for level in BrightnessLevel],
        select_fn=(
            lambda robot, opt: robot.set_panel_brightness(BrightnessLevel[opt.upper()])
        ),
    ),
    FeederRobot: RobotSelectEntityDescription[FeederRobot, float](
        key="meal_insert_size",
        translation_key="meal_insert_size",
        unit_of_measurement="cups",
        current_fn=lambda robot: robot.meal_insert_size,
        options_fn=lambda robot: robot.VALID_MEAL_INSERT_SIZES,
        select_fn=lambda robot, opt: robot.set_meal_insert_size(float(opt)),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot selects using config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LitterRobotSelectEntity(
            robot=robot, coordinator=coordinator, description=description
        )
        for robot in coordinator.account.robots
        for robot_type, description in ROBOT_SELECT_MAP.items()
        if isinstance(robot, robot_type)
    )


class LitterRobotSelectEntity(
    LitterRobotEntity[_WhiskerEntityT],
    SelectEntity,
    Generic[_WhiskerEntityT, _CastTypeT],
):
    """Litter-Robot Select."""

    entity_description: RobotSelectEntityDescription[_WhiskerEntityT, _CastTypeT]

    def __init__(
        self,
        robot: _WhiskerEntityT,
        coordinator: LitterRobotDataUpdateCoordinator,
        description: RobotSelectEntityDescription[_WhiskerEntityT, _CastTypeT],
    ) -> None:
        """Initialize a Litter-Robot select entity."""
        super().__init__(robot, coordinator, description)
        options = self.entity_description.options_fn(self.robot)
        self._attr_options = list(map(str, options))

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return str(self.entity_description.current_fn(self.robot))

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.robot, option)
