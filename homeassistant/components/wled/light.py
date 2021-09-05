"""Support for LED lights."""
from __future__ import annotations

from functools import partial
from typing import Any, Tuple, cast

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_TRANSITION,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_COLOR_PRIMARY,
    ATTR_INTENSITY,
    ATTR_ON,
    ATTR_PALETTE,
    ATTR_PRESET,
    ATTR_REVERSE,
    ATTR_SEGMENT_ID,
    ATTR_SPEED,
    DOMAIN,
    LOGGER,
    SERVICE_EFFECT,
    SERVICE_PRESET,
)
from .coordinator import WLEDDataUpdateCoordinator
from .helpers import wled_exception_handler
from .models import WLEDEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up WLED light based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_EFFECT,
        {
            vol.Optional(ATTR_EFFECT): vol.Any(cv.positive_int, cv.string),
            vol.Optional(ATTR_INTENSITY): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
            vol.Optional(ATTR_PALETTE): vol.Any(cv.positive_int, cv.string),
            vol.Optional(ATTR_REVERSE): cv.boolean,
            vol.Optional(ATTR_SPEED): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        },
        "async_effect",
    )

    platform.async_register_entity_service(
        SERVICE_PRESET,
        {
            vol.Required(ATTR_PRESET): vol.All(
                vol.Coerce(int), vol.Range(min=-1, max=65535)
            ),
        },
        "async_preset",
    )

    if coordinator.keep_master_light:
        async_add_entities([WLEDMasterLight(coordinator=coordinator)])

    update_segments = partial(
        async_update_segments,
        coordinator,
        set(),
        async_add_entities,
    )

    coordinator.async_add_listener(update_segments)
    update_segments()


class WLEDMasterLight(WLEDEntity, LightEntity):
    """Defines a WLED master light."""

    _attr_color_mode = COLOR_MODE_BRIGHTNESS
    _attr_icon = "mdi:led-strip-variant"
    _attr_supported_features = SUPPORT_TRANSITION

    def __init__(self, coordinator: WLEDDataUpdateCoordinator) -> None:
        """Initialize WLED master light."""
        super().__init__(coordinator=coordinator)
        self._attr_name = f"{coordinator.data.info.name} Master"
        self._attr_unique_id = coordinator.data.info.mac_address
        self._attr_supported_color_modes = {COLOR_MODE_BRIGHTNESS}

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
        """Return if this master light is available or not."""
        return self.coordinator.has_master_light and super().available

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

    async def async_effect(
        self,
        effect: int | str | None = None,
        intensity: int | None = None,
        palette: int | str | None = None,
        reverse: bool | None = None,
        speed: int | None = None,
    ) -> None:
        """Set the effect of a WLED light."""
        # Master light does not have an effect setting.

    @wled_exception_handler
    async def async_preset(
        self,
        preset: int,
    ) -> None:
        """Set a WLED light to a saved preset."""
        # The WLED preset service is replaced by a preset select entity
        # and marked deprecated as of Home Assistant 2021.8
        LOGGER.warning(
            "The 'wled.preset' service is deprecated and replaced by a "
            "dedicated preset select entity; Please use that entity to "
            "change presets instead"
        )
        await self.coordinator.wled.preset(preset=preset)


class WLEDSegmentLight(WLEDEntity, LightEntity):
    """Defines a WLED light based on a segment."""

    _attr_supported_features = SUPPORT_EFFECT | SUPPORT_TRANSITION
    _attr_icon = "mdi:led-strip-variant"

    def __init__(
        self,
        coordinator: WLEDDataUpdateCoordinator,
        segment: int,
    ) -> None:
        """Initialize WLED segment light."""
        super().__init__(coordinator=coordinator)
        self._rgbw = coordinator.data.info.leds.rgbw
        self._wv = coordinator.data.info.leds.wv
        self._segment = segment

        # Segment 0 uses a simpler name, which is more natural for when using
        # a single segment / using WLED with one big LED strip.
        self._attr_name = f"{coordinator.data.info.name} Segment {segment}"
        if segment == 0:
            self._attr_name = coordinator.data.info.name

        self._attr_unique_id = (
            f"{self.coordinator.data.info.mac_address}_{self._segment}"
        )

        self._attr_color_mode = COLOR_MODE_RGB
        self._attr_supported_color_modes = {COLOR_MODE_RGB}
        if self._rgbw and self._wv:
            self._attr_color_mode = COLOR_MODE_RGBW
            self._attr_supported_color_modes = {COLOR_MODE_RGBW}

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        try:
            self.coordinator.data.state.segments[self._segment]
        except IndexError:
            return False

        return super().available

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the entity."""
        segment = self.coordinator.data.state.segments[self._segment]
        return {
            ATTR_INTENSITY: segment.intensity,
            ATTR_PALETTE: segment.palette.name,
            ATTR_REVERSE: segment.reverse,
            ATTR_SPEED: segment.speed,
        }

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the color value."""
        return self.coordinator.data.state.segments[self._segment].color_primary[:3]

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the color value."""
        return cast(
            Tuple[int, int, int, int],
            self.coordinator.data.state.segments[self._segment].color_primary,
        )

    @property
    def effect(self) -> str | None:
        """Return the current effect of the light."""
        return self.coordinator.data.state.segments[self._segment].effect.name

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 1..255."""
        state = self.coordinator.data.state

        # If this is the one and only segment, calculate brightness based
        # on the master and segment brightness
        if not self.coordinator.has_master_light:
            return int(
                (state.segments[self._segment].brightness * state.brightness) / 255
            )

        return state.segments[self._segment].brightness

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return [effect.name for effect in self.coordinator.data.effects]

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        state = self.coordinator.data.state

        # If there is no master, we take the master state into account
        # on the segment level.
        if not self.coordinator.has_master_light and not state.on:
            return False

        return bool(state.segments[self._segment].on)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        transition = None
        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            transition = round(kwargs[ATTR_TRANSITION] * 10)

        # If there is no master control, and only 1 segment, handle the
        if not self.coordinator.has_master_light:
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

        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            data[ATTR_TRANSITION] = round(kwargs[ATTR_TRANSITION] * 10)

        if ATTR_BRIGHTNESS in kwargs:
            data[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_EFFECT in kwargs:
            data[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        # If there is no master control, and only 1 segment, handle the master
        if not self.coordinator.has_master_light:
            master_data = {ATTR_ON: True}
            if ATTR_BRIGHTNESS in data:
                master_data[ATTR_BRIGHTNESS] = data[ATTR_BRIGHTNESS]
                data[ATTR_BRIGHTNESS] = 255

            if ATTR_TRANSITION in data:
                master_data[ATTR_TRANSITION] = data[ATTR_TRANSITION]
                del data[ATTR_TRANSITION]

            await self.coordinator.wled.segment(**data)
            await self.coordinator.wled.master(**master_data)
            return

        await self.coordinator.wled.segment(**data)

    @wled_exception_handler
    async def async_effect(
        self,
        effect: int | str | None = None,
        intensity: int | None = None,
        palette: int | str | None = None,
        reverse: bool | None = None,
        speed: int | None = None,
    ) -> None:
        """Set the effect of a WLED light."""
        await self.coordinator.wled.segment(
            segment_id=self._segment,
            effect=effect,
            intensity=intensity,
            palette=palette,
            reverse=reverse,
            speed=speed,
        )

    @wled_exception_handler
    async def async_preset(
        self,
        preset: int,
    ) -> None:
        """Set a WLED light to a saved preset."""
        await self.coordinator.wled.preset(preset=preset)


@callback
def async_update_segments(
    coordinator: WLEDDataUpdateCoordinator,
    current_ids: set[int],
    async_add_entities,
) -> None:
    """Update segments."""
    segment_ids = {light.segment_id for light in coordinator.data.state.segments}
    new_entities: list[WLEDMasterLight | WLEDSegmentLight] = []

    # More than 1 segment now? No master? Add master controls
    if not coordinator.keep_master_light and (
        len(current_ids) < 2 and len(segment_ids) > 1
    ):
        new_entities.append(WLEDMasterLight(coordinator))

    # Process new segments, add them to Home Assistant
    for segment_id in segment_ids - current_ids:
        current_ids.add(segment_id)
        new_entities.append(WLEDSegmentLight(coordinator, segment_id))

    if new_entities:
        async_add_entities(new_entities)
