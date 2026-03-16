"""Support for Litter-Robot switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic

from pylitterbot import FeederRobot, LitterRobot, LitterRobot3, Robot

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, _WhiskerEntityT, whisker_command

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RobotSwitchEntityDescription(SwitchEntityDescription, Generic[_WhiskerEntityT]):
    """A class that describes robot switch entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG
    set_fn: Callable[[_WhiskerEntityT, bool], Coroutine[Any, Any, bool]]
    value_fn: Callable[[_WhiskerEntityT], bool]


NIGHT_LIGHT_MODE_ENTITY_DESCRIPTION = RobotSwitchEntityDescription[
    LitterRobot | FeederRobot
](
    key="night_light_mode_enabled",
    translation_key="night_light_mode",
    set_fn=lambda robot, value: robot.set_night_light(value),
    value_fn=lambda robot: robot.night_light_mode_enabled,
)

SWITCH_MAP: dict[type[Robot], tuple[RobotSwitchEntityDescription, ...]] = {
    FeederRobot: (
        RobotSwitchEntityDescription[FeederRobot](
            key="gravity_mode",
            translation_key="gravity_mode",
            set_fn=lambda robot, value: robot.set_gravity_mode(value),
            value_fn=lambda robot: robot.gravity_mode_enabled,
        ),
        NIGHT_LIGHT_MODE_ENTITY_DESCRIPTION,
    ),
    LitterRobot3: (NIGHT_LIGHT_MODE_ENTITY_DESCRIPTION,),
    Robot: (  # type: ignore[type-abstract]  # only used for isinstance check
        RobotSwitchEntityDescription[LitterRobot | FeederRobot](
            key="panel_lock_enabled",
            translation_key="panel_lockout",
            set_fn=lambda robot, value: robot.set_panel_lockout(value),
            value_fn=lambda robot: robot.panel_lock_enabled,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot switches using config entry."""
    coordinator = entry.runtime_data
    known_robots: set[str] = set()

    def _check_robots() -> None:
        all_robots = coordinator.account.robots
        current_robots = {robot.serial for robot in all_robots}
        new_robots = current_robots - known_robots
        if new_robots:
            known_robots.update(new_robots)
            async_add_entities(
                RobotSwitchEntity(
                    robot=robot, coordinator=coordinator, description=description
                )
                for robot in all_robots
                if robot.serial in new_robots
                for robot_type, entity_descriptions in SWITCH_MAP.items()
                if isinstance(robot, robot_type)
                for description in entity_descriptions
            )

    _check_robots()
    entry.async_on_unload(coordinator.async_add_listener(_check_robots))


class RobotSwitchEntity(LitterRobotEntity[_WhiskerEntityT], SwitchEntity):
    """Litter-Robot switch entity."""

    entity_description: RobotSwitchEntityDescription[_WhiskerEntityT]

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value_fn(self.robot)

    @whisker_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_fn(self.robot, True)

    @whisker_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.robot, False)
