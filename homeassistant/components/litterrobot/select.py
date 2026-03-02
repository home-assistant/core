"""Support for Litter-Robot selects."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pylitterbot import FeederRobot, LitterRobot, LitterRobot4, LitterRobot5, Robot
from pylitterbot.robot.litterrobot4 import BrightnessLevel, NightLightMode
from pylitterbot.robot.litterrobot5 import (
    BrightnessLevel as LR5BrightnessLevel,
    NightLightMode as LR5NightLightMode,
)

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import (
    LitterRobotEntity,
    _WhiskerEntityT,
    async_update_night_light_settings,
    whisker_command,
)

PARALLEL_UPDATES = 1

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
    (LitterRobot4, LitterRobot5): (
        RobotSelectEntityDescription[LitterRobot4 | LitterRobot5, str](
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
            key="night_light_mode",
            translation_key="globe_light",
            current_fn=(
                lambda robot: (
                    mode.name.lower()
                    if (mode := robot.night_light_mode) is not None
                    else None
                )
            ),
            options_fn=lambda _: [mode.name.lower() for mode in LR5NightLightMode],
            select_fn=(
                lambda robot, opt: async_update_night_light_settings(
                    robot, mode=LR5NightLightMode[opt.upper()].value.capitalize()
                )
            ),
        ),
        RobotSelectEntityDescription[LitterRobot5, str](
            key="panel_brightness",
            translation_key="brightness_level",
            current_fn=(
                lambda robot: (
                    bri.name.lower()
                    if (bri := robot.panel_brightness) is not None
                    else None
                )
            ),
            options_fn=lambda _: [level.name.lower() for level in LR5BrightnessLevel],
            select_fn=(
                lambda robot, opt: robot.set_panel_brightness(
                    LR5BrightnessLevel[opt.upper()]
                )
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
    entities: list[SelectEntity] = [
        LitterRobotSelectEntity(
            robot=robot, coordinator=coordinator, description=description
        )
        for robot in coordinator.account.robots
        for robot_type, descriptions in ROBOT_SELECT_MAP.items()
        if isinstance(robot, robot_type)
        for description in descriptions
    ]

    # Add camera view select for LR5 Pro robots with cameras
    entities.extend(
        LitterRobotCameraViewSelect(robot=robot, coordinator=coordinator)
        for robot in coordinator.account.robots
        if isinstance(robot, LitterRobot5) and robot.has_camera
    )

    async_add_entities(entities)


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

    @whisker_command
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.robot, option)
        await self.coordinator.async_request_refresh()


CAMERA_VIEW_OPTIONS = ["front", "globe"]


class LitterRobotCameraViewSelect(LitterRobotEntity[LitterRobot5], SelectEntity):
    """Select entity for switching the camera view on LR5 Pro."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "camera_view"
    _attr_options = CAMERA_VIEW_OPTIONS

    def __init__(
        self,
        robot: LitterRobot5,
        coordinator: LitterRobotDataUpdateCoordinator,
    ) -> None:
        """Initialize the camera view select entity."""
        super().__init__(
            robot,
            coordinator,
            SelectEntityDescription(key="camera_view"),
        )
        self._cached_view: str = "front"

    async def async_added_to_hass(self) -> None:
        """Fetch the current camera view on setup."""
        await super().async_added_to_hass()
        try:
            settings = await self.robot.get_camera_video_settings()
            if settings:
                for item in settings.get("reportedSettings", []):
                    canvas = (
                        item.get("data", {})
                        .get("streams", {})
                        .get("live-view", {})
                        .get("canvas", "")
                    )
                    if "sensor_1" in canvas:
                        self._cached_view = "globe"
                    elif "sensor_0" in canvas:
                        self._cached_view = "front"
        except Exception:  # noqa: BLE001
            pass

    @property
    def current_option(self) -> str:
        """Return the current camera view."""
        return self._cached_view

    async def async_select_option(self, option: str) -> None:
        """Change the camera view."""
        await self.robot.set_camera_view(option)
        self._cached_view = option
        self.async_write_ha_state()
