"""Support for LED lights."""
from functools import partial
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import (
    async_get_registry as async_get_entity_registry,
)
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.color as color_util

from . import WLEDDataUpdateCoordinator, WLEDDeviceEntity, wled_exception_handler
from .const import (
    ATTR_COLOR_PRIMARY,
    ATTR_INTENSITY,
    ATTR_ON,
    ATTR_PALETTE,
    ATTR_PLAYLIST,
    ATTR_PRESET,
    ATTR_REVERSE,
    ATTR_SEGMENT_ID,
    ATTR_SPEED,
    DOMAIN,
    SERVICE_EFFECT,
    SERVICE_PRESET,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up WLED light based on a config entry."""
    coordinator: WLEDDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    platform = entity_platform.current_platform.get()

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

    update_segments = partial(
        async_update_segments, entry, coordinator, {}, async_add_entities
    )

    coordinator.async_add_listener(update_segments)
    update_segments()


class WLEDMasterLight(LightEntity, WLEDDeviceEntity):
    """Defines a WLED master light."""

    def __init__(self, entry_id: str, coordinator: WLEDDataUpdateCoordinator):
        """Initialize WLED master light."""
        super().__init__(
            entry_id=entry_id,
            coordinator=coordinator,
            name=f"{coordinator.data.info.name} Master",
            icon="mdi:led-strip-variant",
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.coordinator.data.info.mac_address}"

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of this light between 1..255."""
        return self.coordinator.data.state.brightness

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        return bool(self.coordinator.data.state.on)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        data = {ATTR_ON: False}

        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            data[ATTR_TRANSITION] = round(kwargs[ATTR_TRANSITION] * 10)

        await self.coordinator.wled.master(**data)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data = {ATTR_ON: True}

        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            data[ATTR_TRANSITION] = round(kwargs[ATTR_TRANSITION] * 10)

        if ATTR_BRIGHTNESS in kwargs:
            data[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]

        await self.coordinator.wled.master(**data)


class WLEDSegmentLight(LightEntity, WLEDDeviceEntity):
    """Defines a WLED light based on a segment."""

    def __init__(
        self, entry_id: str, coordinator: WLEDDataUpdateCoordinator, segment: int
    ):
        """Initialize WLED segment light."""
        self._rgbw = coordinator.data.info.leds.rgbw
        self._segment = segment

        # If this is the one and only segment, use a simpler name
        name = f"{coordinator.data.info.name} Segment {self._segment}"
        if len(coordinator.data.state.segments) == 1:
            name = coordinator.data.info.name

        super().__init__(
            entry_id=entry_id,
            coordinator=coordinator,
            name=name,
            icon="mdi:led-strip-variant",
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.coordinator.data.info.mac_address}_{self._segment}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        try:
            self.coordinator.data.state.segments[self._segment]
        except IndexError:
            return False

        return super().available

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the entity."""
        playlist = self.coordinator.data.state.playlist
        if playlist == -1:
            playlist = None

        preset = self.coordinator.data.state.preset
        if preset == -1:
            preset = None

        segment = self.coordinator.data.state.segments[self._segment]
        return {
            ATTR_INTENSITY: segment.intensity,
            ATTR_PALETTE: segment.palette.name,
            ATTR_PLAYLIST: playlist,
            ATTR_PRESET: preset,
            ATTR_REVERSE: segment.reverse,
            ATTR_SPEED: segment.speed,
        }

    @property
    def hs_color(self) -> Optional[Tuple[float, float]]:
        """Return the hue and saturation color value [float, float]."""
        color = self.coordinator.data.state.segments[self._segment].color_primary
        return color_util.color_RGB_to_hs(*color[:3])

    @property
    def effect(self) -> Optional[str]:
        """Return the current effect of the light."""
        return self.coordinator.data.state.segments[self._segment].effect.name

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of this light between 1..255."""
        state = self.coordinator.data.state

        # If this is the one and only segment, calculate brightness based
        # on the master and segment brightness
        if len(state.segments) == 1:
            return int(
                (state.segments[self._segment].brightness * state.brightness) / 255
            )

        return state.segments[self._segment].brightness

    @property
    def white_value(self) -> Optional[int]:
        """Return the white value of this light between 0..255."""
        color = self.coordinator.data.state.segments[self._segment].color_primary
        return color[-1] if self._rgbw else None

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = (
            SUPPORT_BRIGHTNESS
            | SUPPORT_COLOR
            | SUPPORT_COLOR_TEMP
            | SUPPORT_EFFECT
            | SUPPORT_TRANSITION
        )

        if self._rgbw:
            flags |= SUPPORT_WHITE_VALUE

        return flags

    @property
    def effect_list(self) -> List[str]:
        """Return the list of supported effects."""
        return [effect.name for effect in self.coordinator.data.effects]

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        state = self.coordinator.data.state

        # If there is a single segment, take master into account
        if len(state.segments) == 1 and not state.on:
            return False

        return bool(state.segments[self._segment].on)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        data = {ATTR_ON: False}

        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            data[ATTR_TRANSITION] = round(kwargs[ATTR_TRANSITION] * 10)

        # If there is a single segment, control via the master
        if len(self.coordinator.data.state.segments) == 1:
            await self.coordinator.wled.master(**data)
            return

        data[ATTR_SEGMENT_ID] = self._segment
        await self.coordinator.wled.segment(**data)

    @wled_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        data = {ATTR_ON: True, ATTR_SEGMENT_ID: self._segment}

        if ATTR_COLOR_TEMP in kwargs:
            mireds = color_util.color_temperature_kelvin_to_mired(
                kwargs[ATTR_COLOR_TEMP]
            )
            data[ATTR_COLOR_PRIMARY] = tuple(
                map(int, color_util.color_temperature_to_rgb(mireds))
            )

        if ATTR_HS_COLOR in kwargs:
            hue, sat = kwargs[ATTR_HS_COLOR]
            data[ATTR_COLOR_PRIMARY] = color_util.color_hsv_to_RGB(hue, sat, 100)

        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            data[ATTR_TRANSITION] = round(kwargs[ATTR_TRANSITION] * 10)

        if ATTR_BRIGHTNESS in kwargs:
            data[ATTR_BRIGHTNESS] = kwargs[ATTR_BRIGHTNESS]

        if ATTR_EFFECT in kwargs:
            data[ATTR_EFFECT] = kwargs[ATTR_EFFECT]

        # Support for RGBW strips, adds white value
        if self._rgbw and any(
            x in (ATTR_COLOR_TEMP, ATTR_HS_COLOR, ATTR_WHITE_VALUE) for x in kwargs
        ):
            # WLED cannot just accept a white value, it needs the color.
            # We use the last know color in case just the white value changes.
            if all(x not in (ATTR_COLOR_TEMP, ATTR_HS_COLOR) for x in kwargs):
                hue, sat = self.hs_color
                data[ATTR_COLOR_PRIMARY] = color_util.color_hsv_to_RGB(hue, sat, 100)

            # On a RGBW strip, when the color is pure white, disable the RGB LEDs in
            # WLED by setting RGB to 0,0,0
            if data[ATTR_COLOR_PRIMARY] == (255, 255, 255):
                data[ATTR_COLOR_PRIMARY] = (0, 0, 0)

            # Add requested or last known white value
            if ATTR_WHITE_VALUE in kwargs:
                data[ATTR_COLOR_PRIMARY] += (kwargs[ATTR_WHITE_VALUE],)
            else:
                data[ATTR_COLOR_PRIMARY] += (self.white_value,)

        # When only 1 segment is present, switch along the master, and use
        # the master for power/brightness control.
        if len(self.coordinator.data.state.segments) == 1:
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
        effect: Optional[Union[int, str]] = None,
        intensity: Optional[int] = None,
        palette: Optional[Union[int, str]] = None,
        reverse: Optional[bool] = None,
        speed: Optional[int] = None,
    ) -> None:
        """Set the effect of a WLED light."""
        data = {ATTR_SEGMENT_ID: self._segment}

        if effect is not None:
            data[ATTR_EFFECT] = effect

        if intensity is not None:
            data[ATTR_INTENSITY] = intensity

        if palette is not None:
            data[ATTR_PALETTE] = palette

        if reverse is not None:
            data[ATTR_REVERSE] = reverse

        if speed is not None:
            data[ATTR_SPEED] = speed

        await self.coordinator.wled.segment(**data)

    @wled_exception_handler
    async def async_preset(
        self,
        preset: int,
    ) -> None:
        """Set a WLED light to a saved preset."""
        data = {ATTR_PRESET: preset}

        await self.coordinator.wled.preset(**data)


@callback
def async_update_segments(
    entry: ConfigEntry,
    coordinator: WLEDDataUpdateCoordinator,
    current: Dict[int, WLEDSegmentLight],
    async_add_entities,
) -> None:
    """Update segments."""
    segment_ids = {light.segment_id for light in coordinator.data.state.segments}
    current_ids = set(current)

    # Discard master (if present)
    current_ids.discard(-1)

    # Process new segments, add them to Home Assistant
    new_entities = []
    for segment_id in segment_ids - current_ids:
        current[segment_id] = WLEDSegmentLight(entry.entry_id, coordinator, segment_id)
        new_entities.append(current[segment_id])

    # More than 1 segment now? Add master controls
    if len(current_ids) < 2 and len(segment_ids) > 1:
        current[-1] = WLEDMasterLight(entry.entry_id, coordinator)
        new_entities.append(current[-1])

    if new_entities:
        async_add_entities(new_entities)

    # Process deleted segments, remove them from Home Assistant
    for segment_id in current_ids - segment_ids:
        coordinator.hass.async_create_task(
            async_remove_entity(segment_id, coordinator, current)
        )

    # Remove master if there is only 1 segment left
    if len(current_ids) > 1 and len(segment_ids) < 2:
        coordinator.hass.async_create_task(
            async_remove_entity(-1, coordinator, current)
        )


async def async_remove_entity(
    index: int,
    coordinator: WLEDDataUpdateCoordinator,
    current: Dict[int, WLEDSegmentLight],
) -> None:
    """Remove WLED segment light from Home Assistant."""
    entity = current[index]
    await entity.async_remove()
    registry = await async_get_entity_registry(coordinator.hass)
    if entity.entity_id in registry.entities:
        registry.async_remove(entity.entity_id)
    del current[index]
