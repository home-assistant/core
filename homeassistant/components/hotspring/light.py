"""Support for Hot Spring light entities."""

from typing import Any, cast, override

from hotspring import LightColor, LightZone, Spa

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
        return self._zone.is_on

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        return value_to_brightness((1, 5), self._zone.intensity)

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value."""
        zone = self._zone
        if zone.rgb_state == "active":
            return (zone.c_red, zone.c_green, zone.c_blue)
        return LIGHT_COLOR_TO_RGB.get(zone.color)

    @hotspring_exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if (rgb_color := kwargs.get(ATTR_RGB_COLOR)) is not None:
            await self.coordinator.hotspring.set_light_rgb(self._zone_id, *rgb_color)

        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            intensity = max(1, round(brightness_to_value((1, 5), brightness)))
            await self.coordinator.hotspring.set_light_brightness(
                self._zone_id, intensity
            )
        elif not self.is_on:
            await self.coordinator.hotspring.set_light_brightness(self._zone_id, 5)

        self.coordinator.async_set_updated_data(
            cast(Spa, self.coordinator.hotspring.spa)
        )

    @hotspring_exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.coordinator.hotspring.turn_off_light(self._zone_id)
        self.coordinator.async_set_updated_data(
            cast(Spa, self.coordinator.hotspring.spa)
        )
