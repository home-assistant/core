"""Support for LED lights."""

from functools import partial
from typing import Any, cast, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.group import IntegrationSpecificGroup

from .const import (
    ATTR_CCT,
    ATTR_COLOR_PRIMARY,
    ATTR_ON,
    ATTR_SEGMENT_ID,
    COLOR_TEMP_K_MAX,
    COLOR_TEMP_K_MIN,
    LIGHT_CAPABILITIES_COLOR_MODE_MAPPING,
)
from .coordinator import WLEDConfigEntry, WLEDDataUpdateCoordinator
from .entity import WLEDEntity
from .helpers import kelvin_to_255, kelvin_to_255_reverse, wled_exception_handler

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WLEDConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    group: IntegrationSpecificGroup

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED main light."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = coordinator.data.info.mac_address
        self.group = IntegrationSpecificGroup(self, [])
        self._update_group_member()

    def _update_group_member(self) -> None:
        """Update group members based on current segments."""
        segment_unique_ids = [
            f"{self.coordinator.data.info.mac_address}_{segment_id}"
            for segment_id in sorted(self.coordinator.segment_ids)
        ]
        if segment_unique_ids != self.group.member_unique_ids:
            self.group.member_unique_ids = segment_unique_ids

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        return self.coordinator.data.state.brightness

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the light."""
        return bool(self.coordinator.data.state.on)

    @property
    @override
    def available(self) -> bool:
        """Return if this main light is available or not."""
        return self.coordinator.has_main_light and super().available

    @wled_exception_handler
    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        transition = None
        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            transition = round(kwargs[ATTR_TRANSITION] * 10)

        await self.coordinator.wled.master(on=False, transition=transition)

    @wled_exception_handler
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        transition = None
        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            transition = round(kwargs[ATTR_TRANSITION] * 10)

        await self.coordinator.wled.master(
            on=True, brightness=kwargs.get(ATTR_BRIGHTNESS), transition=transition
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._update_group_member()
        super()._handle_coordinator_update()


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
            self._infer_color_mode()

    @callback
    def _infer_color_mode(self) -> None:
        """Infer the color mode from the current color of the segment.

        WLED does not track the color mode used, so derive it from the color.
        Only applies to RGB lights with color temperature support: RGBWW lights
        stay in RGBWW mode, so the cold/warm white channels keep being
        reported. Only a dedicated white channel or pure white RGB is color
        temperature, any other grey (r == g == b) is a regular RGB color.
        """
        if (
            not self._attr_supported_color_modes
            or ColorMode.RGB not in self._attr_supported_color_modes
            or ColorMode.COLOR_TEMP not in self._attr_supported_color_modes
            or self._segment not in self.coordinator.data.state.segments
        ):
            return

        color = self.coordinator.data.state.segments[self._segment].color
        if not color or not color.primary:
            return

        r, g, b, w = (*color.primary, 0, 0, 0, 0)[:4]
        self._attr_color_mode = (
            ColorMode.COLOR_TEMP
            if (r == g == b == 0 and w > 0) or (r == g == b == 255 and w == 0)
            else ColorMode.RGB
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self._segment in self.coordinator.data.state.segments
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Update attributes when the coordinator updates."""
        self._infer_color_mode()
        super()._handle_coordinator_update()

    @property
    @override
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the color value."""
        if not (color := self.coordinator.data.state.segments[self._segment].color):
            return None
        return color.primary[:3]

    @property
    @override
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the color value."""
        if not (color := self.coordinator.data.state.segments[self._segment].color):
            return None
        return cast(tuple[int, int, int, int], color.primary)

    @property
    @override
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return rgbww color value from WLED rgb+cct color value."""
        state = self.coordinator.data.state
        seg = state.segments[self._segment]
        if not (color := seg.color) or not color.primary:
            return None

        r, g, b = color.primary[:3]
        w_brightness = color.primary[3] if len(color.primary) > 3 else 0
        cct = seg.cct

        if cct <= 127:
            # At low CCT values (warm end), keep warm white at full
            # brightness and scale in cold white as CCT increases.
            ww = w_brightness
            cw = round(cct * w_brightness / 127)
        else:
            # At high CCT values (cold end), keep cold white at full
            # brightness and scale out warm white as CCT increases.
            cw = w_brightness
            ww = round((255 - cct) * w_brightness / 128)

        # Home Assistant expects rgbww_color as (r, g, b, cold_white, warm_white).
        return (r, g, b, cw, ww)

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in K."""
        cct = self.coordinator.data.state.segments[self._segment].cct
        return kelvin_to_255_reverse(cct, COLOR_TEMP_K_MIN, COLOR_TEMP_K_MAX)

    @property
    @override
    def effect(self) -> str | None:
        """Return the current effect of the light."""
        return self.coordinator.data.effects[
            int(self.coordinator.data.state.segments[self._segment].effect_id)
        ].name

    @property
    @override
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        state = self.coordinator.data.state

        # If this is the one and only segment, calculate brightness based
        # on the main and segment brightness
        segment_brightness = int(state.segments[self._segment].brightness)
        if not self.coordinator.has_main_light:
            return int((segment_brightness * state.brightness) / 255)

        return segment_brightness

    @property
    @override
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return [effect.name for effect in self.coordinator.data.effects.values()]

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the light."""
        state = self.coordinator.data.state

        # If there is no main, we take the main state into account
        # on the segment level.
        if not self.coordinator.has_main_light and not state.on:
            return False

        return bool(state.segments[self._segment].on)

    @wled_exception_handler
    @override
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
    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data: dict[str, Any] = {
            ATTR_ON: True,
            ATTR_SEGMENT_ID: self._segment,
        }

        if ATTR_RGB_COLOR in kwargs:
            # if the light supports cct reset white balance to white to not distort colors
            if (
                self._attr_supported_color_modes
                and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
            ):
                data[ATTR_CCT] = 127

            data[ATTR_COLOR_PRIMARY] = kwargs[ATTR_RGB_COLOR]

        if ATTR_RGBW_COLOR in kwargs:
            # if the light supports cct reset white balance to white to not distort colors
            if (
                self._attr_supported_color_modes
                and ColorMode.COLOR_TEMP in self._attr_supported_color_modes
            ):
                data[ATTR_CCT] = 127

            data[ATTR_COLOR_PRIMARY] = kwargs[ATTR_RGBW_COLOR]

        if ATTR_RGBWW_COLOR in kwargs:
            # HA sends: (Red, Green, Blue, ColdWhite, WarmWhite)
            r, g, b, cw, ww = kwargs[ATTR_RGBWW_COLOR]

            w_brightness = max(cw, ww)

            if w_brightness == 0:
                cct = 127
            elif ww == w_brightness:
                cct = round(cw * 127 / w_brightness)
            else:
                cct = 255 - round(ww * 128 / w_brightness)

            data[ATTR_COLOR_PRIMARY] = (r, g, b, w_brightness)
            data[ATTR_CCT] = cct

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            if self._attr_supported_color_modes:
                has_rgb = ColorMode.RGB in self._attr_supported_color_modes
                has_rgbw = ColorMode.RGBW in self._attr_supported_color_modes
                has_rgbww = ColorMode.RGBWW in self._attr_supported_color_modes

                if has_rgb:
                    data[ATTR_COLOR_PRIMARY] = (255, 255, 255, 0)

                if has_rgbw or has_rgbww:
                    data[ATTR_COLOR_PRIMARY] = (0, 0, 0, 255)

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
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Update segments."""
    segment_ids = coordinator.segment_ids
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
