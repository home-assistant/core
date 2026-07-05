"""Support for Litter-Robot night light."""

from typing import Any, override

from pylitterbot import LitterRobot5
from pylitterbot.robot.litterrobot4 import NightLightMode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry
from .entity import LitterRobotEntity, whisker_command

PARALLEL_UPDATES = 1

NIGHT_LIGHT_DESCRIPTION = LightEntityDescription(
    key="night_light",
    translation_key="night_light",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot night light using config entry."""
    coordinator = entry.runtime_data
    known_robots: set[str] = set()

    def _check_robots() -> None:
        all_robots = [
            robot
            for robot in coordinator.account.robots
            if isinstance(robot, LitterRobot5)
        ]
        current_robots = {robot.serial for robot in all_robots}
        new_robots = current_robots - known_robots
        if new_robots:
            known_robots.update(new_robots)
            async_add_entities(
                LitterRobotNightLight(robot, coordinator, NIGHT_LIGHT_DESCRIPTION)
                for robot in all_robots
                if robot.serial in new_robots
            )

    _check_robots()
    entry.async_on_unload(coordinator.async_add_listener(_check_robots))


class LitterRobotNightLight(LitterRobotEntity[LitterRobot5], LightEntity):
    """Representation of the night light on a Litter-Robot 5."""

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the night light is on (any mode other than off)."""
        mode = self.robot.night_light_mode
        return mode is not None and mode is not NightLightMode.OFF

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of the night light, scaled to 0-255."""
        return round(self.robot.night_light_brightness * 255 / 100)

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the color of the night light."""
        return self.robot.night_light_rgb_color

    @whisker_command
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the night light, applying any requested color or brightness."""
        mode = self.robot.night_light_mode
        brightness = self.robot.night_light_brightness
        color: str | tuple[int, int, int] = self.robot.night_light_color or "#FFFFFF"

        if ATTR_RGB_COLOR in kwargs:
            color = kwargs[ATTR_RGB_COLOR]

        if ATTR_BRIGHTNESS in kwargs:
            brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
        # Preserve the auto mode when the light is already on; otherwise switch on.
        if mode is None or mode is NightLightMode.OFF:
            mode = NightLightMode.ON

        # The API replaces the entire settings object, so send every field.
        await self.robot.set_night_light_settings(
            mode=mode, brightness=brightness, color=color
        )

    @whisker_command
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the night light."""
        await self.robot.set_night_light_settings(mode=NightLightMode.OFF)
