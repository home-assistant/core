"""Support for Litter-Robot selects."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
import itertools
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotConfigEntity, _RobotT
from .hub import LitterRobotHub


@dataclass
class RequiredKeysMixin(Generic[_RobotT]):
    """A class that describes robot select entity required keys."""

    current_fn: Callable[[_RobotT], int | float]
    options_fn: Callable[[_RobotT], list]
    select_fn: Callable[[_RobotT], Callable[..., Coroutine[Any, Any, bool]]]


@dataclass
class RobotSelectEntityDescription(SelectEntityDescription, RequiredKeysMixin[_RobotT]):
    """A class that describes robot select entities."""

    cast_type: type[int | float] = field(default=int)


@dataclass
class FeederRobotSelectEntityDescription(RobotSelectEntityDescription[FeederRobot]):
    """A class that describes Feeder-Robot select entities."""

    cast_type: type[float] = field(default=float)


LITTER_ROBOT_SELECT = RobotSelectEntityDescription[LitterRobot](
    key="clean_cycle_wait_time_minutes",
    name="Clean Cycle Wait Time Minutes",
    icon="mdi:timer-outline",
    current_fn=lambda robot: robot.clean_cycle_wait_time_minutes,
    options_fn=lambda robot: robot.VALID_WAIT_TIMES,
    select_fn=lambda robot: robot.set_wait_time,
)
FEEDER_ROBOT_SELECT = FeederRobotSelectEntityDescription(
    key="meal_insert_size",
    name="Meal insert size",
    icon="mdi:scale",
    unit_of_measurement="cups",
    current_fn=lambda robot: robot.meal_insert_size,
    options_fn=lambda robot: robot.VALID_MEAL_INSERT_SIZES,
    select_fn=lambda robot: robot.set_meal_insert_size,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot selects using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
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


class LitterRobotSelect(LitterRobotConfigEntity[_RobotT], SelectEntity):
    """Litter-Robot Select."""

    entity_description: RobotSelectEntityDescription[_RobotT]

    def __init__(
        self,
        robot: _RobotT,
        hub: LitterRobotHub,
        description: RobotSelectEntityDescription[_RobotT],
    ) -> None:
        """Initialize a Litter-Robot select entity."""
        assert description.name
        super().__init__(robot, description.name, hub)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        current_value = self.entity_description.current_fn(self.robot)
        return None if current_value is None else str(current_value)

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return [
            str(option) for option in self.entity_description.options_fn(self.robot)
        ]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if select_fn := self.entity_description.select_fn(self.robot):
            await self.perform_action_and_refresh(
                select_fn, self.entity_description.cast_type(option)
            )
