"""Support for LED lights."""

from __future__ import annotations

from functools import partial
from typing import Any, cast

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WLEDConfigEntry
from .const import (
    ATTR_CCT,
    ATTR_COLOR_PRIMARY,
    ATTR_ON,
    ATTR_SEGMENT_ID,
    COLOR_TEMP_K_MAX,
    COLOR_TEMP_K_MIN,
    LIGHT_CAPABILITIES_COLOR_MODE_MAPPING,
)
from .coordinator import WLEDDataUpdateCoordinator
from .entity import WLEDEntity
from .helpers import kelvin_to_255, kelvin_to_255_reverse, wled_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED light based on a config entry."""
    coordinator = entry.runtime_data
    if coordinator.keep_main_light:
        async_add_entities([WLEDMainLight(coordinator=coordinator)])

    update_segments = partial(
        async_update_segments,
        coordinator,
        set(),
        async_add_entities,
    )

    coordinator.async_add_listener(update_segments)
    update_segments()


class WLEDMainLight(WLEDEntity, LightEntity):
    """Defines a WLED main light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_translation_key = "main"
    _attr_supported_features = LightEntityFeature.TRANSITION
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED main light."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = coordinator.data.info.mac_address

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        return self.coordinator.data.state.brightness

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        return bool(self.coordinator.data.state.on)

    @property
    def available(self) -> bool:
        """Return if this main light is available or not."""
        return self.coordinator.has_main_light and super().available

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        transition = None
        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            transition = round(kwargs[ATTR_TRANSITION] * 10)

        await self.coordinator.wled.master(on=False, transition=transition)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        transition = None
        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            transition = round(kwargs[ATTR_TRANSITION] * 10)

        await self.coordinator.wled.master(
            on=True, brightness=kwargs.get(ATTR_BRIGHTNESS), transition=transition
        )


class WLEDSegmentLight(WLEDEntity, LightEntity):
    """Defines a WLED light based on a segment."""

    _attr_supported_features = LightEntityFeature.EFFECT | LightEntityFeature.TRANSITION
    _attr_translation_key = "segment"
    _attr_min_color_temp_kelvin = COLOR_TEMP_K_MIN
    _attr_max_color_temp_kelvin = COLOR_TEMP_K_MAX

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        segment: int,
    ) -> None:
        """Initialize WLED segment light."""
        super().__init__(coordinator=coordinator)
        self._segment = segment

        # Segment 0 uses a simpler name, which is more natural for when using
        # a single segment / using WLED with one big LED strip.
        if segment == 0:
            self._attr_name = None
        else:
            self._attr_translation_placeholders = {"segment": str(segment)}

        self._attr_unique_id = (
            f"{self.coordinator.data.info.mac_address}_{self._segment}"
        )

        if (
            coordinator.data.info.leds.segment_light_capabilities is not None
            and (
                color_modes := LIGHT_CAPABILITIES_COLOR_MODE_MAPPING.get(
                    coordinator.data.info.leds.segment_light_capabilities[segment]
                )
            )
            is not None
        ):
            self._attr_color_mode = color_modes[0]
            self._attr_supported_color_modes = set(color_modes)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        try:
            self.coordinator.data.state.segments[self._segment]
        except KeyError:
            return False

        return super().available

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the color value."""
        if not (color := self.coordinator.data.state.segments[self._segment].color):
            return None
        return color.primary[:3]

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the color value."""
        if not (color := self.coordinator.data.state.segments[self._segment].color):
            return None
        return cast(tuple[int, int, int, int], color.primary)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in K."""
        cct = self.coordinator.data.state.segments[self._segment].cct
        return kelvin_to_255_reverse(cct, COLOR_TEMP_K_MIN, COLOR_TEMP_K_MAX)

    @property
    def effect(self) -> str | None:
        """Return the current effect of the light."""
        return self.coordinator.data.effects[
            int(self.coordinator.data.state.segments[self._segment].effect_id)
        ].name

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        state = self.coordinator.data.state

        # If this is the one and only segment, calculate brightness based
        # on the main and segment brightness
        if not self.coordinator.has_main_light:
            return int(
                (state.segments[self._segment].brightness * state.brightness) / 255
            )

        return state.segments[self._segment].brightness

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return [effect.name for effect in self.coordinator.data.effects.values()]

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        state = self.coordinator.data.state

        # If there is no main, we take the main state into account
        # on the segment level.
        if not self.coordinator.has_main_light and not state.on:
            return False

        return bool(state.segments[self._segment].on)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        transition = None
        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            transition = round(kwargs[ATTR_TRANSITION] * 10)

        # If there is no main control, and only 1 segment, handle the main
        if not self.coordinator.has_main_light:
            await self.coordinator.wled.master(on=False, transition=transition)
            return

        await self.coordinator.wled.segment(
            segment_id=self._segment, on=False, transition=transition
        )

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data: dict[str, Any] = {
            ATTR_ON: True,
            ATTR_SEGMENT_ID: self._segment,
        }

        if ATTR_RGB_COLOR in kwargs:
            data[ATTR_COLOR_PRIMARY] = kwargs[ATTR_RGB_COLOR]

        if ATTR_RGBW_COLOR in kwargs:
            data[ATTR_COLOR_PRIMARY] = kwargs[ATTR_RGBW_COLOR]

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            data[ATTR_CCT] = kelvin_to_255(
                kwargs[ATTR_COLOR_TEMP_KELVIN], COLOR_TEMP_K_MIN, COLOR_TEMP_K_MAX
            )

        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            data[ATTR_TRANSITION] = round(kwargs[ATTR_TRANSITION] * 10)

        if ATTR_BRIGHTNESS in kwargs:
            data[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_EFFECT in kwargs:
            data[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        # If there is no main control, and only 1 segment, handle the main
        if not self.coordinator.has_main_light:
            main_data = {ATTR_ON: True}
            if ATTR_BRIGHTNESS in data:
                main_data[ATTR_BRIGHTNESS] = data[ATTR_BRIGHTNESS]
                data[ATTR_BRIGHTNESS] = 255

            if ATTR_TRANSITION in data:
                main_data[ATTR_TRANSITION] = data[ATTR_TRANSITION]
                del data[ATTR_TRANSITION]

            await self.coordinator.wled.segment(**data)
            await self.coordinator.wled.master(**main_data)
            return

        await self.coordinator.wled.segment(**data)


@callback
def async_update_segments(
    coordinator: WLEDDataUpdateCoordinator,
    current_ids: set[int],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Update segments."""
    segment_ids = {
        light.segment_id
        for light in coordinator.data.state.segments.values()
        if light.segment_id is not None
    }
    new_entities: list[WLEDMainLight | WLEDSegmentLight] = []

    # More than 1 segment now? No main? Add main controls
    if not coordinator.keep_main_light and (
        len(current_ids) < 2 and len(segment_ids) > 1
    ):
        new_entities.append(WLEDMainLight(coordinator))

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current_ids.add(segment_id)
        new_entities.append(WLEDSegmentLight(coordinator, segment_id))

    async_add_entities(new_entities)
