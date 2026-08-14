"""Support for Litter-Robot switches."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from functools import partial
from typing import Any, Generic, override

from pylitterbot import FeederRobot, LitterRobot, LitterRobot3, LitterRobot5, Robot
from pylitterbot.sleep_schedule import DayOfWeek

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry
from .entity import (
    LitterRobotEntity,
    _WhiskerEntityT,
    raise_update_failed,
    whisker_command,
)

PARALLEL_UPDATES = 1


def _lr5_sleep_day_enabled(robot: LitterRobot5, *, day: DayOfWeek) -> bool:
    """Return whether a day's sleep schedule is enabled."""
    if (schedule := robot.sleep_schedule) is None:
        return False
    return (entry := schedule.get_day(day)) is not None and entry.is_enabled


async def _lr5_set_sleep_day_enabled(
    robot: LitterRobot5, value: bool, *, day: DayOfWeek
) -> bool:
    """Enable or disable a day's sleep schedule, preserving its times."""
    return await robot.set_sleep_mode(value, day_of_week=day)


@dataclass(frozen=True, kw_only=True)
class RobotSwitchEntityDescription(SwitchEntityDescription, Generic[_WhiskerEntityT]):  # noqa: UP046
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
    LitterRobot5: tuple(
        RobotSwitchEntityDescription[LitterRobot5](
            key=f"sleep_mode_{day.name.lower()}",
            translation_key=f"sleep_mode_{day.name.lower()}",
            entity_registry_enabled_default=False,
            set_fn=partial(_lr5_set_sleep_day_enabled, day=day),
            value_fn=partial(_lr5_sleep_day_enabled, day=day),
        )
        for day in DayOfWeek
    ),
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
    @override
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.entity_description.value_fn(self.robot)

    @whisker_command
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if not await self.entity_description.set_fn(self.robot, True):
            raise_update_failed(self.entity_id)

    @whisker_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if not await self.entity_description.set_fn(self.robot, False):
            raise_update_failed(self.entity_id)
