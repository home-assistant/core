"""Support for Litter-Robot selects."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
import itertools
from typing import Any

from pylitterbot import FeederRobot, LitterRobot, Robot

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotConfigEntity
from .hub import LitterRobotHub


@dataclass
class RobotSelectEntityDescription(SelectEntityDescription):
    """A class that describes robot select entities."""

    options_fn: Callable[[Robot], list] = lambda _: []
    select_fn: Callable[
        [Robot], Callable[..., Coroutine[Any, Any, bool]] | None
    ] = lambda _: None
    cast_type: type[int | float] = field(default=int)


@dataclass
class LitterRobotSelectEntityDescription(RobotSelectEntityDescription):
    """A class that describes Litter-Robot select entities."""

    options_fn: Callable[[LitterRobot], list] = lambda _: []
    select_fn: Callable[
        [LitterRobot], Callable[..., Coroutine[Any, Any, bool]] | None
    ] = lambda _: None


@dataclass
class FeederRobotSelectEntityDescription(RobotSelectEntityDescription):
    """A class that describes Feeder-Robot select entities."""

    options_fn: Callable[[FeederRobot], list] = lambda _: []
    select_fn: Callable[
        [FeederRobot], Callable[..., Coroutine[Any, Any, bool]] | None
    ] = lambda _: None
    cast_type: type[float] = field(default=float)


LITTER_ROBOT_SELECT = LitterRobotSelectEntityDescription(
    key="clean_cycle_wait_time_minutes",
    name="Clean Cycle Wait Time Minutes",
    icon="mdi:timer-outline",
    options_fn=lambda robot: robot.VALID_WAIT_TIMES,
    select_fn=lambda robot: robot.set_wait_time,
)
FEEDER_ROBOT_SELECT = FeederRobotSelectEntityDescription(
    key="meal_insert_size",
    name="Meal insert size",
    icon="mdi:scale",
    unit_of_measurement="cups",
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


class LitterRobotSelect(LitterRobotConfigEntity[LitterRobot], SelectEntity):
    """Litter-Robot Select."""

    entity_description: RobotSelectEntityDescription

    def __init__(
        self,
        robot: Robot,
        hub: LitterRobotHub,
        description: RobotSelectEntityDescription,
    ) -> None:
        """Initialize a Litter-Robot select entity."""
        assert description.name
        super().__init__(robot, description.name, hub)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return str(getattr(self.robot, self.entity_description.key))

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
