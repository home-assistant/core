"""Support for LED lights."""
import logging
from typing import Any, Callable, List, Optional, Tuple

from wled import WLED, Effect, WLEDError

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
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.color as color_util

from . import WLEDDeviceEntity
from .const import (
    ATTR_COLOR_PRIMARY,
    ATTR_INTENSITY,
    ATTR_ON,
    ATTR_PALETTE,
    ATTR_PLAYLIST,
    ATTR_PRESET,
    ATTR_SEGMENT_ID,
    ATTR_SPEED,
    DATA_WLED_CLIENT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up WLED light based on a config entry."""
    wled: WLED = hass.data[DOMAIN][entry.entry_id][DATA_WLED_CLIENT]

    # Does the WLED device support RGBW
    rgbw = wled.device.info.leds.rgbw

    # List of supported effects
    effects = wled.device.effects

    # WLED supports splitting a strip in multiple segments
    # Each segment will be a separate light in Home Assistant
    lights = []
    for light in wled.device.state.segments:
        lights.append(WLEDLight(entry.entry_id, wled, light.segment_id, rgbw, effects))

    async_add_entities(lights, True)


class WLEDLight(Light, WLEDDeviceEntity):
    """Defines a WLED light."""

    def __init__(
        self, entry_id: str, wled: WLED, segment: int, rgbw: bool, effects: List[Effect]
    ):
        """Initialize WLED light."""
        self._effects = effects
        self._rgbw = rgbw
        self._segment = segment

        self._brightness: Optional[int] = None
        self._color: Optional[Tuple[float, float]] = None
        self._effect: Optional[str] = None
        self._state: Optional[bool] = None
        self._white_value: Optional[int] = None

        # Only apply the segment ID if it is not the first segment
        name = wled.device.info.name
        if segment != 0:
            name += f" {segment}"

        super().__init__(entry_id, wled, name, "mdi:led-strip-variant")

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self.wled.device.info.mac_address}_{self._segment}"

    @property
    def hs_color(self) -> Optional[Tuple[float, float]]:
        """Return the hue and saturation color value [float, float]."""
        return self._color

    @property
    def effect(self) -> Optional[str]:
        """Return the current effect of the light."""
        return self._effect

    @property
    def brightness(self) -> Optional[int]:
        """Return the brightness of this light between 1..255."""
        return self._brightness

    @property
    def white_value(self) -> Optional[int]:
        """Return the white value of this light between 0..255."""
        return self._white_value

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
        return [effect.name for effect in self._effects]

    @property
    def is_on(self) -> bool:
        """Return the state of the light."""
        return bool(self._state)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        data = {ATTR_ON: False, ATTR_SEGMENT_ID: self._segment}

        if ATTR_TRANSITION in kwargs:
            # WLED uses 100ms per unit, so 10 = 1 second.
            data[ATTR_TRANSITION] = round(kwargs[ATTR_TRANSITION] * 10)

        try:
            await self.wled.light(**data)
            self._state = False
        except WLEDError:
            _LOGGER.error("An error occurred while turning off WLED light.")
            self._available = False
        self.async_schedule_update_ha_state()

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
            if not any(x in (ATTR_COLOR_TEMP, ATTR_HS_COLOR) for x in kwargs):
                hue, sat = self._color
                data[ATTR_COLOR_PRIMARY] = color_util.color_hsv_to_RGB(hue, sat, 100)

            # On a RGBW strip, when the color is pure white, disable the RGB LEDs in
            # WLED by setting RGB to 0,0,0
            if data[ATTR_COLOR_PRIMARY] == (255, 255, 255):
                data[ATTR_COLOR_PRIMARY] = (0, 0, 0)

            # Add requested or last known white value
            if ATTR_WHITE_VALUE in kwargs:
                data[ATTR_COLOR_PRIMARY] += (kwargs[ATTR_WHITE_VALUE],)
            else:
                data[ATTR_COLOR_PRIMARY] += (self._white_value,)

        try:
            await self.wled.light(**data)

            self._state = True

            if ATTR_BRIGHTNESS in kwargs:
                self._brightness = kwargs[ATTR_BRIGHTNESS]

            if ATTR_EFFECT in kwargs:
                self._effect = kwargs[ATTR_EFFECT]

            if ATTR_HS_COLOR in kwargs:
                self._color = kwargs[ATTR_HS_COLOR]

            if ATTR_COLOR_TEMP in kwargs:
                self._color = color_util.color_temperature_to_hs(mireds)

            if ATTR_WHITE_VALUE in kwargs:
                self._white_value = kwargs[ATTR_WHITE_VALUE]

        except WLEDError:
            _LOGGER.error("An error occurred while turning on WLED light.")
            self._available = False
        self.async_schedule_update_ha_state()

    async def _wled_update(self) -> None:
        """Update WLED entity."""
        self._brightness = self.wled.device.state.brightness
        self._effect = self.wled.device.state.segments[self._segment].effect.name
        self._state = self.wled.device.state.on

        color = self.wled.device.state.segments[self._segment].color_primary
        self._color = color_util.color_RGB_to_hs(*color[:3])
        if self._rgbw:
            self._white_value = color[-1]

        playlist = self.wled.device.state.playlist
        if playlist == -1:
            playlist = None

        preset = self.wled.device.state.preset
        if preset == -1:
            preset = None

        self._attributes = {
            ATTR_INTENSITY: self.wled.device.state.segments[self._segment].intensity,
            ATTR_PALETTE: self.wled.device.state.segments[self._segment].palette.name,
            ATTR_PLAYLIST: playlist,
            ATTR_PRESET: preset,
            ATTR_SPEED: self.wled.device.state.segments[self._segment].speed,
        }
