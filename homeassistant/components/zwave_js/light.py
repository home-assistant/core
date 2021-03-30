"""Support for Z-Wave lights."""
from __future__ import annotations

import logging
from typing import Any, Callable

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import ColorComponent, CommandClass

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    DOMAIN as LIGHT_DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.color as color_util

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)

MULTI_COLOR_MAP = {
    ColorComponent.WARM_WHITE: "warmWhite",
    ColorComponent.COLD_WHITE: "coldWhite",
    ColorComponent.RED: "red",
    ColorComponent.GREEN: "green",
    ColorComponent.BLUE: "blue",
    ColorComponent.AMBER: "amber",
    ColorComponent.CYAN: "cyan",
    ColorComponent.PURPLE: "purple",
}


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave Light from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_light(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Light."""

        light = ZwaveLight(config_entry, client, info)
        async_add_entities([light])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{LIGHT_DOMAIN}",
            async_add_light,
        )
    )


def byte_to_zwave_brightness(value: int) -> int:
    """Convert brightness in 0-255 scale to 0-99 scale.

    `value` -- (int) Brightness byte value from 0-255.
    """
    if value > 0:
        return max(1, round((value / 255) * 99))
    return 0


class ZwaveLight(ZWaveBaseEntity, LightEntity):
    """Representation of a Z-Wave light."""

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the light."""
        super().__init__(config_entry, client, info)
        self._supports_color = False
        self._supports_white_value = False
        self._supports_color_temp = False
        self._hs_color: tuple[float, float] | None = None
        self._white_value: int | None = None
        self._color_temp: int | None = None
        self._min_mireds = 153  # 6500K as a safe default
        self._max_mireds = 370  # 2700K as a safe default
        self._supported_features = SUPPORT_BRIGHTNESS

        # get additional (optional) values and set features
        self._target_value = self.get_zwave_value("targetValue")
        self._dimming_duration = self.get_zwave_value("duration")
        if self._dimming_duration is not None:
            self._supported_features |= SUPPORT_TRANSITION
        self._calculate_color_values()
        if self._supports_color:
            self._supported_features |= SUPPORT_COLOR
        if self._supports_color_temp:
            self._supported_features |= SUPPORT_COLOR_TEMP
        if self._supports_white_value:
            self._supported_features |= SUPPORT_WHITE_VALUE

    @callback
    def on_value_update(self) -> None:
        """Call when a watched value is added or updated."""
        self._calculate_color_values()

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255.

        Z-Wave multilevel switches use a range of [0, 99] to control brightness.
        """
        if self.info.primary_value.value is not None:
            return round((self.info.primary_value.value / 99) * 255)
        return 0

    @property
    def is_on(self) -> bool:
        """Return true if device is on (brightness above 0)."""
        return self.brightness > 0

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color."""
        return self._hs_color

    @property
    def white_value(self) -> int | None:
        """Return the white value of this light between 0..255."""
        return self._white_value

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature."""
        return self._color_temp

    @property
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        return self._min_mireds

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        return self._max_mireds

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        # RGB/HS color
        hs_color = kwargs.get(ATTR_HS_COLOR)
        if hs_color is not None and self._supports_color:
            red, green, blue = color_util.color_hs_to_RGB(*hs_color)
            colors = {
                ColorComponent.RED: red,
                ColorComponent.GREEN: green,
                ColorComponent.BLUE: blue,
            }
            if self._supports_color_temp:
                # turn of white leds when setting rgb
                colors[ColorComponent.WARM_WHITE] = 0
                colors[ColorComponent.COLD_WHITE] = 0
            await self._async_set_colors(colors)

        # Color temperature
        color_temp = kwargs.get(ATTR_COLOR_TEMP)
        if color_temp is not None and self._supports_color_temp:
            # Limit color temp to min/max values
            cold = max(
                0,
                min(
                    255,
                    round(
                        (self._max_mireds - color_temp)
                        / (self._max_mireds - self._min_mireds)
                        * 255
                    ),
                ),
            )
            warm = 255 - cold
            await self._async_set_colors(
                {
                    # turn off color leds when setting color temperature
                    ColorComponent.RED: 0,
                    ColorComponent.GREEN: 0,
                    ColorComponent.BLUE: 0,
                    ColorComponent.WARM_WHITE: warm,
                    ColorComponent.COLD_WHITE: cold,
                }
            )

        # White value
        white_value = kwargs.get(ATTR_WHITE_VALUE)
        if white_value is not None and self._supports_white_value:
            # white led brightness is controlled by white level
            # rgb leds (if any) can be on at the same time
            await self._async_set_colors(
                {
                    ColorComponent.WARM_WHITE: white_value,
                    ColorComponent.COLD_WHITE: white_value,
                }
            )

        # set brightness
        await self._async_set_brightness(
            kwargs.get(ATTR_BRIGHTNESS), kwargs.get(ATTR_TRANSITION)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_set_brightness(0, kwargs.get(ATTR_TRANSITION))

    async def _async_set_colors(self, colors: dict[ColorComponent, int]) -> None:
        """Set (multiple) defined colors to given value(s)."""
        # prefer the (new) combined color property
        # https://github.com/zwave-js/node-zwave-js/pull/1782
        combined_color_val = self.get_zwave_value(
            "targetColor",
            CommandClass.SWITCH_COLOR,
            value_property_key=None,
        )
        if combined_color_val and isinstance(combined_color_val.value, dict):
            colors_dict = {}
            for color, value in colors.items():
                color_name = MULTI_COLOR_MAP[color]
                colors_dict[color_name] = value
            # set updated color object
            await self.info.node.async_set_value(combined_color_val, colors_dict)
            return

        # fallback to setting the color(s) one by one if multicolor fails
        # not sure this is needed at all, but just in case
        for color, value in colors.items():
            await self._async_set_color(color, value)

    async def _async_set_color(self, color: ColorComponent, new_value: int) -> None:
        """Set defined color to given value."""
        # actually set the new color value
        target_zwave_value = self.get_zwave_value(
            "targetColor",
            CommandClass.SWITCH_COLOR,
            value_property_key=color.value,
        )
        if target_zwave_value is None:
            # guard for unsupported color
            return
        await self.info.node.async_set_value(target_zwave_value, new_value)

    async def _async_set_brightness(
        self, brightness: int | None, transition: int | None = None
    ) -> None:
        """Set new brightness to light."""
        if brightness is None:
            # Level 255 means to set it to previous value.
            zwave_brightness = 255
        else:
            # Zwave multilevel switches use a range of [0, 99] to control brightness.
            zwave_brightness = byte_to_zwave_brightness(brightness)

        # set transition value before sending new brightness
        await self._async_set_transition_duration(transition)
        # setting a value requires setting targetValue
        await self.info.node.async_set_value(self._target_value, zwave_brightness)

    async def _async_set_transition_duration(self, duration: int | None = None) -> None:
        """Set the transition time for the brightness value."""
        if self._dimming_duration is None:
            return
        # pylint: disable=fixme,unreachable
        # TODO: setting duration needs to be fixed upstream
        # https://github.com/zwave-js/node-zwave-js/issues/1321
        return

        if duration is None:  # type: ignore
            # no transition specified by user, use defaults
            duration = 7621  # anything over 7620 uses the factory default
        else:  # pragma: no cover
            # transition specified by user
            transition = duration
            if transition <= 127:
                duration = transition
            else:
                minutes = round(transition / 60)
                LOGGER.debug(
                    "Transition rounded to %d minutes for %s",
                    minutes,
                    self.entity_id,
                )
                duration = minutes + 128

        # only send value if it differs from current
        # this prevents sending a command for nothing
        if self._dimming_duration.value != duration:  # pragma: no cover
            await self.info.node.async_set_value(self._dimming_duration, duration)

    @callback
    def _calculate_color_values(self) -> None:
        """Calculate light colors."""
        # NOTE: We lookup all values here (instead of relying on the multicolor one)
        # to find out what colors are supported
        # as this is a simple lookup by key, this not heavy
        red_val = self.get_zwave_value(
            "currentColor",
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.RED.value,
        )
        green_val = self.get_zwave_value(
            "currentColor",
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.GREEN.value,
        )
        blue_val = self.get_zwave_value(
            "currentColor",
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.BLUE.value,
        )
        ww_val = self.get_zwave_value(
            "currentColor",
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.WARM_WHITE.value,
        )
        cw_val = self.get_zwave_value(
            "currentColor",
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.COLD_WHITE.value,
        )
        # prefer the (new) combined color property
        # https://github.com/zwave-js/node-zwave-js/pull/1782
        combined_color_val = self.get_zwave_value(
            "currentColor",
            CommandClass.SWITCH_COLOR,
            value_property_key=None,
        )
        if combined_color_val and isinstance(combined_color_val.value, dict):
            multi_color = combined_color_val.value
        else:
            multi_color = {}

        # RGB support
        if red_val and green_val and blue_val:
            # prefer values from the multicolor property
            red = multi_color.get("red", red_val.value)
            green = multi_color.get("green", green_val.value)
            blue = multi_color.get("blue", blue_val.value)
            self._supports_color = True
            # convert to HS
            self._hs_color = color_util.color_RGB_to_hs(red, green, blue)

        # color temperature support
        if ww_val and cw_val:
            self._supports_color_temp = True
            warm_white = multi_color.get("warmWhite", ww_val.value)
            cold_white = multi_color.get("coldWhite", cw_val.value)
            # Calculate color temps based on whites
            if cold_white or warm_white:
                self._color_temp = round(
                    self._max_mireds
                    - ((cold_white / 255) * (self._max_mireds - self._min_mireds))
                )
            else:
                self._color_temp = None
        # only one white channel (warm white) = white_level support
        elif ww_val:
            self._supports_white_value = True
            self._white_value = multi_color.get("warmWhite", ww_val.value)
        # only one white channel (cool white) = white_level support
        elif cw_val:
            self._supports_white_value = True
            self._white_value = multi_color.get("coldWhite", cw_val.value)
