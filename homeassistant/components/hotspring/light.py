"""Support for Hot Spring light entities."""

from typing import Any, override

from hotspring import LightColor, LightZone

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from .coordinator import HotSpringConfigEntry, HotSpringDataUpdateCoordinator
from .entity import HotSpringEntity
from .helpers import hotspring_exception_handler

PARALLEL_UPDATES = 1

LIGHT_COLOR_TO_RGB: dict[LightColor, tuple[int, int, int]] = {
    LightColor.RED: (255, 0, 0),
    LightColor.GREEN: (0, 255, 0),
    LightColor.BLUE: (0, 0, 255),
    LightColor.YELLOW: (255, 255, 0),
    LightColor.WHITE: (255, 255, 255),
    LightColor.AQUA: (0, 255, 255),
    LightColor.MAGENTA: (255, 0, 255),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HotSpringConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Hot Spring light entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        HotSpringLightEntity(coordinator, zone.zone_id)
        for zone in coordinator.data.light_zones
        if zone.is_enabled
    )


class HotSpringLightEntity(HotSpringEntity, LightEntity):
    """Defines a Hot Spring light entity."""

    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_translation_key = "light_zone"

    def __init__(
        self,
        coordinator: HotSpringDataUpdateCoordinator,
        zone_id: int,
    ) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator, f"light_zone_{zone_id}")
        self._zone_id = zone_id
        self._attr_translation_placeholders = {"zone": str(zone_id)}

    @property
    def _zone(self) -> LightZone:
        """Return the light zone data."""
        for zone in self.coordinator.data.light_zones:
            if zone.zone_id == self._zone_id:
                return zone
        raise AssertionError("Light zone must exist in coordinator data")

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the light is on."""
        return self._zone.intensity > 0

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        if self._zone.intensity <= 0:
            return None
        return value_to_brightness((1, 5), self._zone.intensity)

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value."""
        return LIGHT_COLOR_TO_RGB.get(self._zone.color)

    @hotspring_exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        zone = self._zone

        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            intensity = round(brightness_to_value((1, 5), brightness))
        elif zone.intensity > 0:
            intensity = zone.intensity
        else:
            intensity = 5

        if (rgb_color := kwargs.get(ATTR_RGB_COLOR)) is not None:
            r, g, b = rgb_color
            await self.coordinator.hotspring.set_light_rgb(self._zone_id, r, g, b)
            if zone.intensity <= 0 or ATTR_BRIGHTNESS in kwargs:
                color = (
                    zone.color.value
                    if zone.color in LIGHT_COLOR_TO_RGB
                    else LightColor.WHITE.value
                )
                await self.coordinator.hotspring.set_light_color(
                    self._zone_id,
                    color=color,
                    intensity=intensity,
                )
            await self.coordinator.async_request_refresh()
            return

        if zone.color in LIGHT_COLOR_TO_RGB:
            color = zone.color.value
        else:
            color = LightColor.WHITE.value

        await self.coordinator.hotspring.set_light_color(
            self._zone_id,
            color=color,
            intensity=intensity,
        )
        await self.coordinator.async_request_refresh()

    @hotspring_exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.hotspring.turn_off_light(self._zone_id)
        await self.coordinator.async_request_refresh()
