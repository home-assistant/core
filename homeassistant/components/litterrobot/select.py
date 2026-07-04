"""Support for Litter-Robot selects."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, override

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4, LitterRobot5, Robot
from pylitterbot.robot.litterrobot4 import BrightnessLevel, NightLightMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import LitterRobotEntity, _WhiskerEntityT, whisker_command

PARALLEL_UPDATES = 1

_CastTypeT = TypeVar("_CastTypeT", int, float, str)

# The LED does not necessarily render an arbitrary RGB value as the same color
# at every brightness level (an LR5 firmware quirk, like the non-monotonic
# brightness mapping below). These presets are verified on hardware to render
# true at all brightness levels and are offered as known-good options while the
# light's RGB picker stays available for custom colors.
NIGHT_LIGHT_PRESETS: dict[str, str] = {
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "cyan": "#00FFFF",
    "magenta": "#FF00FF",
    "yellow": "#FFFF00",
    "white": "#FFFFFF",
}

# The LR5 globe LED renders brightness non-monotonically (a firmware quirk also
# present in the Whisker app), so LOW/MEDIUM/HIGH map to the percentages that
# read as dim/medium/bright on the LR5 rather than the LR4 25/50/100 levels. The
# light entity exposes the full continuous range.
LR5_GLOBE_BRIGHTNESS: dict[str, int] = {"low": 10, "medium": 100, "high": 75}


def _active_night_light_preset(robot: LitterRobot5) -> str | None:
    """Return the preset matching the current color, or None for a custom color."""
    if (color := robot.night_light_color) is None:
        return None
    # The device may echo an 8-digit #RRGGBBAA value; compare on the RGB part.
    normalized = "#" + color.lstrip("#").upper()[:6]
    return next(
        (name for name, value in NIGHT_LIGHT_PRESETS.items() if value == normalized),
        None,
    )


@dataclass(frozen=True, kw_only=True)
class RobotSelectEntityDescription(
    SelectEntityDescription,
    Generic[_WhiskerEntityT, _CastTypeT],  # noqa: UP046
):
    """A class that describes robot select entities."""

    entity_category: EntityCategory = EntityCategory.CONFIG
    current_fn: Callable[[_WhiskerEntityT], _CastTypeT | None]
    options_fn: Callable[[_WhiskerEntityT], list[_CastTypeT]]
    select_fn: Callable[[_WhiskerEntityT, str], Coroutine[Any, Any, bool]]


ROBOT_SELECT_MAP: dict[
    type[Robot] | tuple[type[Robot], ...], tuple[RobotSelectEntityDescription, ...]
] = {
    LitterRobot: (
        RobotSelectEntityDescription[LitterRobot, int](
            key="cycle_delay",
            translation_key="cycle_delay",
            unit_of_measurement=UnitOfTime.MINUTES,
            current_fn=lambda robot: robot.clean_cycle_wait_time_minutes,
            options_fn=lambda robot: robot.VALID_WAIT_TIMES,
            select_fn=lambda robot, opt: robot.set_wait_time(int(opt)),
        ),
    ),
    # LR4 globe brightness uses the device's discrete BrightnessLevel enum
    # (25/50/100). LR5 has its own globe_brightness below with eye-calibrated
    # percentages, since LR5 firmware renders brightness non-monotonically.
    LitterRobot4: (
        RobotSelectEntityDescription[LitterRobot4, str](
            key="globe_brightness",
            translation_key="globe_brightness",
            current_fn=(
                lambda robot: (
                    bri.name.lower()
                    if (bri := robot.night_light_level) is not None
                    else None
                )
            ),
            options_fn=lambda _: [level.name.lower() for level in BrightnessLevel],
            select_fn=(
                lambda robot, opt: robot.set_night_light_brightness(
                    BrightnessLevel[opt.upper()]
                )
            ),
        ),
    ),
    (LitterRobot4, LitterRobot5): (
        RobotSelectEntityDescription[LitterRobot4 | LitterRobot5, str](
            key="globe_light",
            translation_key="globe_light",
            current_fn=(
                lambda robot: (
                    mode.name.lower()
                    if (mode := robot.night_light_mode) is not None
                    else None
                )
            ),
            options_fn=lambda _: [mode.name.lower() for mode in NightLightMode],
            select_fn=(
                lambda robot, opt: robot.set_night_light_mode(
                    NightLightMode[opt.upper()]
                )
            ),
        ),
        RobotSelectEntityDescription[LitterRobot4 | LitterRobot5, str](
            key="panel_brightness",
            translation_key="brightness_level",
            current_fn=(
                lambda robot: (
                    bri.name.lower()
                    if (bri := robot.panel_brightness) is not None
                    else None
                )
            ),
            options_fn=lambda _: [level.name.lower() for level in BrightnessLevel],
            select_fn=(
                lambda robot, opt: robot.set_panel_brightness(
                    BrightnessLevel[opt.upper()]
                )
            ),
        ),
    ),
    LitterRobot5: (
        RobotSelectEntityDescription[LitterRobot5, str](
            key="globe_brightness",
            translation_key="globe_brightness",
            current_fn=lambda robot: next(
                (
                    level
                    for level, pct in LR5_GLOBE_BRIGHTNESS.items()
                    if pct == robot.night_light_brightness
                ),
                None,
            ),
            options_fn=lambda _: list(LR5_GLOBE_BRIGHTNESS),
            select_fn=lambda robot, opt: robot.set_night_light_brightness(
                LR5_GLOBE_BRIGHTNESS[opt]
            ),
        ),
        RobotSelectEntityDescription[LitterRobot5, str](
            key="night_light_preset",
            translation_key="night_light_preset",
            current_fn=_active_night_light_preset,
            options_fn=lambda _: list(NIGHT_LIGHT_PRESETS),
            select_fn=lambda robot, opt: robot.set_night_light_settings(
                # The API replaces the whole object, so keep mode + brightness.
                mode=robot.night_light_mode or NightLightMode.ON,
                brightness=robot.night_light_brightness,
                color=NIGHT_LIGHT_PRESETS[opt],
            ),
        ),
    ),
    FeederRobot: (
        RobotSelectEntityDescription[FeederRobot, float](
            key="meal_insert_size",
            translation_key="meal_insert_size",
            unit_of_measurement="cups",
            current_fn=lambda robot: robot.meal_insert_size,
            options_fn=lambda robot: robot.VALID_MEAL_INSERT_SIZES,
            select_fn=lambda robot, opt: robot.set_meal_insert_size(float(opt)),
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot selects using config entry."""
    coordinator = entry.runtime_data
    known_robots: set[str] = set()

    def _check_robots() -> None:
        all_robots = coordinator.account.robots
        current_robots = {robot.serial for robot in all_robots}
        new_robots = current_robots - known_robots
        if new_robots:
            known_robots.update(new_robots)
            async_add_entities(
                LitterRobotSelectEntity(
                    robot=robot, coordinator=coordinator, description=description
                )
                for robot in all_robots
                if robot.serial in new_robots
                for robot_type, descriptions in ROBOT_SELECT_MAP.items()
                if isinstance(robot, robot_type)
                for description in descriptions
            )

    _check_robots()
    entry.async_on_unload(coordinator.async_add_listener(_check_robots))


class LitterRobotSelectEntity(
    LitterRobotEntity[_WhiskerEntityT],
    SelectEntity,
    Generic[_WhiskerEntityT, _CastTypeT],  # noqa: UP046
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
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        option = self.entity_description.current_fn(self.robot)
        return None if option is None else str(option)

    @whisker_command
    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.robot, option)
