"""Support for Litter-Robot button."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import itertools
from typing import Any

from pylitterbot import FeederRobot, LitterRobot3

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LitterRobotEntity
from .hub import LitterRobotHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Litter-Robot cleaner using config entry."""
    hub: LitterRobotHub = hass.data[DOMAIN][entry.entry_id]
    entities = itertools.chain(
        (
            LitterRobotButtonEntity(
                robot=robot, hub=hub, description=LITTER_ROBOT_BUTTON
            )
            for robot in hub.litter_robots()
            if isinstance(robot, LitterRobot3)
        ),
        (
            LitterRobotButtonEntity(
                robot=robot, hub=hub, description=FEEDER_ROBOT_BUTTON
            )
            for robot in hub.feeder_robots()
        ),
    )
    async_add_entities(entities)


@dataclass
class RobotButtonEntityDescription(ButtonEntityDescription):
    """A class that describes robot button entities."""

    press_fn: Callable[
        [LitterRobot3 | FeederRobot], Coroutine[Any, Any, bool] | None
    ] = lambda _: None


@dataclass
class LitterRobotButtonEntityDescription(RobotButtonEntityDescription):
    """A class that describes Litter-Robot button entities."""

    press_fn: Callable[
        [LitterRobot3], Coroutine[Any, Any, bool] | None
    ] = lambda _: None


@dataclass
class FeederRobotButtonEntityDescription(RobotButtonEntityDescription):
    """A class that describes Feeder-Robot button entities."""

    press_fn: Callable[[FeederRobot], Coroutine[Any, Any, bool] | None] = lambda _: None


LITTER_ROBOT_BUTTON = LitterRobotButtonEntityDescription(
    key="reset_waste_drawer",
    name="Reset Waste Drawer",
    icon="mdi:delete-variant",
    entity_category=EntityCategory.CONFIG,
    press_fn=lambda robot: robot.reset_waste_drawer(),
)
FEEDER_ROBOT_BUTTON = FeederRobotButtonEntityDescription(
    key="give_snack",
    name="Give snack",
    icon="mdi:candy-outline",
    press_fn=lambda robot: robot.give_snack(),
)


class LitterRobotButtonEntity(LitterRobotEntity[LitterRobot3], ButtonEntity):
    """Litter-Robot button entity."""

    entity_description: RobotButtonEntityDescription
    robot: LitterRobot3 | FeederRobot

    def __init__(
        self,
        robot: LitterRobot3 | FeederRobot,
        hub: LitterRobotHub,
        description: RobotButtonEntityDescription,
    ) -> None:
        """Initialize a Litter-Robot button entity."""
        assert description.name
        super().__init__(robot, description.name, hub)
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        if action := self.entity_description.press_fn(self.robot):
            await action
            self.coordinator.async_set_updated_data(True)
