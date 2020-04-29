"""Support for LED lights."""
import logging
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
    Light,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity import Entity
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
)

_LOGGER = logging.getLogger(__name__)

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
            vol.Optional(ATTR_REVERSE): cv.boolean,
            vol.Optional(ATTR_SPEED): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        },
        "async_effect",
    )

    lights = [
        WLEDLight(entry.entry_id, coordinator, light.segment_id)
        for light in coordinator.data.state.segments
    ]

    async_add_entities(lights, True)


class WLEDLight(Light, WLEDDeviceEntity):
    """Defines a WLED light."""

    def __init__(
        self, entry_id: str, coordinator: WLEDDataUpdateCoordinator, segment: int
    ):
        """Initialize WLED light."""
        self._rgbw = coordinator.data.info.leds.rgbw
        self._segment = segment

        # Only apply the segment ID if it is not the first segment
        name = coordinator.data.info.name
        if segment != 0:
            name += f" {segment}"

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
        return self.coordinator.data.state.brightness

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
        return bool(self.coordinator.data.state.on)

    @wled_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        data = {ATTR_ON: False, ATTR_SEGMENT_ID: self._segment}

        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            data[ATTR_TRANSITION] = round(kwargs[ATTR_TRANSITION] * 10)

        await self.coordinator.wled.light(**data)

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

        await self.coordinator.wled.light(**data)

    @wled_exception_handler
    async def async_effect(
        self,
        effect: Optional[Union[int, str]] = None,
        intensity: Optional[int] = None,
        reverse: Optional[bool] = None,
        speed: Optional[int] = None,
    ) -> None:
        """Set the effect of a WLED light."""
        data = {ATTR_SEGMENT_ID: self._segment}

        if effect is not None:
            data[ATTR_EFFECT] = effect

        if intensity is not None:
            data[ATTR_INTENSITY] = intensity

        if reverse is not None:
            data[ATTR_REVERSE] = reverse

        if speed is not None:
            data[ATTR_SPEED] = speed

        await self.coordinator.wled.light(**data)
