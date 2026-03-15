"""Support for Litter-Robot light entities."""

from __future__ import annotations

from typing import Any

from pylitterbot import LitterRobot5
from pylitterbot.robot.litterrobot5 import NightLightMode as LR5NightLightMode

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .entity import (
    LitterRobotEntity,
    async_update_night_light_settings,
    whisker_command,
)

NIGHT_LIGHT_DESCRIPTION = LightEntityDescription(
    key="night_light",
    translation_key="night_light",
)


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert a hex color string to an RGB tuple."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    elif len(h) == 4:
        h = "".join(c * 2 for c in h[:3])
    elif len(h) == 8:
        h = h[:6]
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LitterRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Litter-Robot light entities using config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        LitterRobotNightLight(robot=robot, coordinator=coordinator)
        for robot in coordinator.account.robots
        if isinstance(robot, LitterRobot5)
    )


class LitterRobotNightLight(LitterRobotEntity[LitterRobot5], LightEntity):
    """Litter-Robot 5 night light with RGB color support."""

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_translation_key = "night_light"

    def __init__(
        self,
        robot: LitterRobot5,
        coordinator: LitterRobotDataUpdateCoordinator,
    ) -> None:
        """Initialize a Litter-Robot night light entity."""
        super().__init__(robot, coordinator, NIGHT_LIGHT_DESCRIPTION)

    _attr_is_on: bool | None = None
    _attr_brightness: int | None = None
    _attr_rgb_color: tuple[int, int, int] | None = None

    @property
    def is_on(self) -> bool:
        """Return true if the night light mode is not OFF."""
        if self._attr_is_on is not None:
            return self._attr_is_on
        mode = self.robot.night_light_mode
        return mode is not None and mode != LR5NightLightMode.OFF

    @property
    def brightness(self) -> int | None:
        """Return the brightness (0-255)."""
        if self._attr_brightness is not None:
            return self._attr_brightness
        bri = self.robot.night_light_brightness
        if bri is None:
            return None
        return round(bri * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color value."""
        if self._attr_rgb_color is not None:
            return self._attr_rgb_color
        color = self.robot.night_light_color
        if color is None:
            return None
        return _hex_to_rgb(color)

    def _clear_optimistic_state(self) -> None:
        """Clear optimistic state so next read uses robot data."""
        self._attr_is_on = None
        self._attr_brightness = None
        self._attr_rgb_color = None

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._clear_optimistic_state()
        super()._handle_coordinator_update()

    @whisker_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the night light with optional brightness and color."""
        updates: dict[str, Any] = {}

        if ATTR_BRIGHTNESS in kwargs:
            ha_brightness = kwargs[ATTR_BRIGHTNESS]
            updates["brightness"] = round(ha_brightness * 100 / 255)
            self._attr_brightness = ha_brightness

        if ATTR_RGB_COLOR in kwargs:
            r, g, b = kwargs[ATTR_RGB_COLOR]
            updates["color"] = f"{r:02X}{g:02X}{b:02X}"
            self._attr_rgb_color = (r, g, b)

        if not self.is_on:
            updates["mode"] = LR5NightLightMode.ON.value.capitalize()
            self._attr_is_on = True
        elif not updates:
            return

        self.async_write_ha_state()
        await async_update_night_light_settings(self.robot, **updates)

    @whisker_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the night light."""
        self._attr_is_on = False
        self.async_write_ha_state()
        await async_update_night_light_settings(
            self.robot, mode=LR5NightLightMode.OFF.value.capitalize()
        )
