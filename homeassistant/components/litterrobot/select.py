"""Support for Litter-Robot selects."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4, Robot
from pylitterbot.robot.litterrobot4 import BrightnessLevel

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity, _RobotT
from .hub import LitterRobotHub

_CastTypeT = TypeVar("_CastTypeT", int, float, str)

BRIGHTNESS_LEVEL_ICON_MAP: dict[BrightnessLevel | None, str] = {
    BrightnessLevel.LOW: "mdi:lightbulb-on-30",
    BrightnessLevel.MEDIUM: "mdi:lightbulb-on-50",
    BrightnessLevel.HIGH: "mdi:lightbulb-on",
    None: "mdi:lightbulb-question",
}


@dataclass
class RequiredKeysMixin(Generic[_RobotT, _CastTypeT]):
    """A class that describes robot select entity required keys."""

    current_fn: Callable[[_RobotT], _CastTypeT | None]
    options_fn: Callable[[_RobotT], list[_CastTypeT]]
    select_fn: Callable[[_RobotT, str], Coroutine[Any, Any, bool]]


@dataclass
class RobotSelectEntityDescription(
    SelectEntityDescription, RequiredKeysMixin[_RobotT, _CastTypeT]
):
    """A class that describes robot select entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG
    icon_fn: Callable[[_RobotT], str] | None = None


ROBOT_SELECT_MAP: dict[type[Robot], RobotSelectEntityDescription] = {
    LitterRobot: RobotSelectEntityDescription[LitterRobot, int](  # type: ignore[type-abstract]  # only used for isinstance check
        key="cycle_delay",
        translation_key="cycle_delay",
        icon="mdi:timer-outline",
        unit_of_measurement=UnitOfTime.MINUTES,
        current_fn=lambda robot: robot.clean_cycle_wait_time_minutes,
        options_fn=lambda robot: robot.VALID_WAIT_TIMES,
        select_fn=lambda robot, opt: robot.set_wait_time(int(opt)),
    ),
    LitterRobot4: RobotSelectEntityDescription[LitterRobot4, str](
        key="panel_brightness",
        translation_key="brightness_level",
        current_fn=lambda robot: bri.name.lower()
        if (bri := robot.panel_brightness) is not None
        else None,
        options_fn=lambda _: [level.name.lower() for level in BrightnessLevel],
        select_fn=lambda robot, opt: robot.set_panel_brightness(
            BrightnessLevel[opt.upper()]
        ),
        icon_fn=lambda robot: BRIGHTNESS_LEVEL_ICON_MAP[robot.panel_brightness],
    ),
    FeederRobot: RobotSelectEntityDescription[FeederRobot, float](
        key="meal_insert_size",
        translation_key="meal_insert_size",
        icon="mdi:scale",
        unit_of_measurement="cups",
        current_fn=lambda robot: robot.meal_insert_size,
        options_fn=lambda robot: robot.VALID_MEAL_INSERT_SIZES,
        select_fn=lambda robot, opt: robot.set_meal_insert_size(float(opt)),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot selects using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][config_entry.entry_id]
    entities = [
        LitterRobotSelectEntity(robot=robot, hub=hub, description=description)
        for robot in hub.account.robots
        for robot_type, description in ROBOT_SELECT_MAP.items()
        if isinstance(robot, robot_type)
    ]
    async_add_entities(entities)


class LitterRobotSelectEntity(
    LitterRobotEntity[_RobotT], SelectEntity, Generic[_RobotT, _CastTypeT]
):
    """Litter-Robot Select."""

    entity_description: RobotSelectEntityDescription[_RobotT, _CastTypeT]

    def __init__(
        self,
        robot: _RobotT,
        hub: LitterRobotHub,
        description: RobotSelectEntityDescription[_RobotT, _CastTypeT],
    ) -> None:
        """Initialize a Litter-Robot select entity."""
        super().__init__(robot, hub, description)
        options = self.entity_description.options_fn(self.robot)
        self._attr_options = list(map(str, options))

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend, if any."""
        if icon_fn := self.entity_description.icon_fn:
            return str(icon_fn(self.robot))
        return super().icon

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return str(self.entity_description.current_fn(self.robot))

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.robot, option)
