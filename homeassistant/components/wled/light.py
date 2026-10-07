"""Support for LED lights."""

from functools import partial
from typing import Any, cast, override

from wled import Device as WLEDDevice, LightCapability, combine_white, split_white

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


def _has_warm_and_cold_white(device: WLEDDevice, segment: int) -> bool:
    """Return whether a segment's white is split over warm and cold white.

    That takes LEDs with separate warm and cold white on every output the
    segment is on, and WLED using the color temperature for them, rather
    than calculating it from the RGB color.
    """
    capabilities = device.state.segments[segment].light_capabilities
    if (
        capabilities is None
        or (
            LightCapability.RGB_COLOR
            | LightCapability.WHITE_CHANNEL
            | LightCapability.COLOR_TEMPERATURE
        )
        not in capabilities
        or device.led_config is None
        or device.led_config.cct_from_rgb
    ):
        return False

    outputs = device.segment_led_outputs(segment)
    return bool(outputs) and all(
        output.has_rgb and output.has_white and output.has_cct for output in outputs
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

        self._color_modes: list[ColorMode] = []
        self._has_white_channel = False
        if (
            capabilities := coordinator.data.state.segments[segment].light_capabilities
        ) is not None and (
            color_modes := LIGHT_CAPABILITIES_COLOR_MODE_MAPPING.get(capabilities)
        ) is not None:
            # With separate warm and cold white, the white channel holds both.
            if _has_warm_and_cold_white(coordinator.data, segment):
                color_modes = [ColorMode.COLOR_TEMP, ColorMode.RGBWW]
            self._color_modes = color_modes
            self._attr_supported_color_modes = set(color_modes)
            self._has_white_channel = LightCapability.WHITE_CHANNEL in capabilities

    @property
    @override
    def color_mode(self) -> ColorMode | None:
        """Return the color mode the segment is in right now.

        WLED doesn't tell, so it follows from the color: a color temperature
        shows as full white, on the white channel when there is one.
        """
        if not self._color_modes:
            return None

        if len(self._color_modes) == 1:
            return self._color_modes[0]

        # A color temperature shows as exactly the white this light sends for
        # it. A dimmed white channel is a color, so restoring it doesn't turn
        # it into full white.
        color = self.coordinator.data.state.segments[self._segment].color
        if ColorMode.COLOR_TEMP in self._color_modes and color is not None:
            primary = color.primary
            if (
                primary == (0, 0, 0, 255)
                if self._has_white_channel
                else primary[:3] == (255, 255, 255)
            ):
                return ColorMode.COLOR_TEMP

        return next(
            mode for mode in self._color_modes if mode is not ColorMode.COLOR_TEMP
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available and self._segment in self.coordinator.data.state.segments
        )

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
        """Return the color value, with the white split over cold and warm."""
        segment = self.coordinator.data.state.segments[self._segment]
        if not (color := segment.color):
            return None

        red, green, blue, *white = color.primary
        warm, cold = split_white(
            white[0] if white else 0, segment.cct, cct_blend=self._cct_blend
        )
        return (red, green, blue, cold, warm)

    @property
    def _cct_blend(self) -> int:
        """Return how the device blends warm and cold white, in percent."""
        if (led_config := self.coordinator.data.led_config) is None:
            return 0
        return led_config.cct_blend

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
            data[ATTR_COLOR_PRIMARY] = kwargs[ATTR_RGB_COLOR]

        if ATTR_RGBW_COLOR in kwargs:
            data[ATTR_COLOR_PRIMARY] = kwargs[ATTR_RGBW_COLOR]

        if ATTR_RGBWW_COLOR in kwargs:
            red, green, blue, cold, warm = kwargs[ATTR_RGBWW_COLOR]
            white, data[ATTR_CCT] = combine_white(warm, cold, cct_blend=self._cct_blend)
            data[ATTR_COLOR_PRIMARY] = (red, green, blue, white)

        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            data[ATTR_CCT] = kelvin_to_255(
                kwargs[ATTR_COLOR_TEMP_KELVIN], COLOR_TEMP_K_MIN, COLOR_TEMP_K_MAX
            )
            # A color temperature only shows on white light: the white channel
            # where there is one, otherwise full white.
            if self._color_modes:
                data[ATTR_COLOR_PRIMARY] = (
                    (0, 0, 0, 255) if self._has_white_channel else (255, 255, 255)
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
