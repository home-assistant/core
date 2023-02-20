"""Support for Litter-Robot selects."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import itertools
from typing import Any, Generic, TypeVar

from pylitterbot import FeederRobot, LitterRobot

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity, _RobotT
from .hub import LitterRobotHub

_CastTypeT = TypeVar("_CastTypeT", int, float)


@dataclass
class RequiredKeysMixin(Generic[_RobotT, _CastTypeT]):
    """A class that describes robot select entity required keys."""

    current_fn: Callable[[_RobotT], _CastTypeT]
    options_fn: Callable[[_RobotT], list[_CastTypeT]]
    select_fn: Callable[[_RobotT, str], Coroutine[Any, Any, bool]]


@dataclass
class RobotSelectEntityDescription(
    SelectEntityDescription, RequiredKeysMixin[_RobotT, _CastTypeT]
):
    """A class that describes robot select entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG


LITTER_ROBOT_SELECT = RobotSelectEntityDescription[LitterRobot, int](
    key="cycle_delay",
    name="Clean cycle wait time minutes",
    icon="mdi:timer-outline",
    unit_of_measurement=UnitOfTime.MINUTES,
    current_fn=lambda robot: robot.clean_cycle_wait_time_minutes,
    options_fn=lambda robot: robot.VALID_WAIT_TIMES,
    select_fn=lambda robot, option: robot.set_wait_time(int(option)),
)
FEEDER_ROBOT_SELECT = RobotSelectEntityDescription[FeederRobot, float](
    key="meal_insert_size",
    name="Meal insert size",
    icon="mdi:scale",
    unit_of_measurement="cups",
    current_fn=lambda robot: robot.meal_insert_size,
    options_fn=lambda robot: robot.VALID_MEAL_INSERT_SIZES,
    select_fn=lambda robot, option: robot.set_meal_insert_size(float(option)),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot selects using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[LitterRobotSelect] = list(
        itertools.chain(
            (
                LitterRobotSelect(robot=robot, hub=hub, description=LITTER_ROBOT_SELECT)
                for robot in hub.litter_robots()
            ),
            (
                LitterRobotSelect(robot=robot, hub=hub, description=FEEDER_ROBOT_SELECT)
                for robot in hub.feeder_robots()
            ),
        )
    )
    async_add_entities(entities)


class LitterRobotSelect(
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
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return str(self.entity_description.current_fn(self.robot))

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.robot, option)
