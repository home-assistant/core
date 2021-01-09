"""Support for Z-Wave lights."""
import logging
from typing import Callable, List, Optional

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import CommandClass

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

COLOR_CHANNEL_WARM_WHITE = 0x01
COLOR_CHANNEL_COLD_WHITE = 0x02
COLOR_CHANNEL_RED = 0x04
COLOR_CHANNEL_GREEN = 0x08
COLOR_CHANNEL_BLUE = 0x10


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave Light from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_light(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Light."""

        light = ZwaveLight(client, info)
        async_add_entities([light])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_add_{LIGHT_DOMAIN}", async_add_light)
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

    def __init__(self, client: ZwaveClient, info: ZwaveDiscoveryInfo) -> None:
        """Initialize the light."""
        super().__init__(client, info)
        self._supports_color = False
        self._supports_white_value = False
        self._supports_color_temp = False
        self._hs_color = None
        self._white_value = None
        self._color_temp = None
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
        if self._target_value is not None and self._target_value.value is not None:
            return round((self._target_value.value / 99) * 255)
        if self.info.primary_value.value is not None:
            return round((self.info.primary_value.value / 99) * 255)
        return 0

    @property
    def is_on(self) -> bool:
        """Return true if device is on (brightness above 0)."""
        return self.brightness > 0

    @property
    def hs_color(self) -> Optional[List]:
        """Return the hs color."""
        return self._hs_color

    @property
    def white_value(self) -> Optional[int]:
        """Return the white value of this light between 0..255."""
        return self._white_value

    @property
    def color_temp(self) -> Optional[int]:
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
    def supported_features(self) -> Optional[int]:
        """Flag supported features."""
        return self._supported_features

    async def async_turn_on(self, **kwargs: dict) -> None:
        """Turn the device on."""
        # RGB/HS color
        hs_color = kwargs.get(ATTR_HS_COLOR)
        if hs_color is not None and self._supports_color:
            red, green, blue = color_util.color_hs_to_RGB(*hs_color)
            target_val = self.get_zwave_value("targetColor", property_key_name="Red")
            await self.info.node.async_set_value(target_val, red)
            target_val = self.get_zwave_value("targetColor", property_key_name="Green")
            await self.info.node.async_set_value(target_val, green)
            target_val = self.get_zwave_value("targetColor", property_key_name="Blue")
            await self.info.node.async_set_value(target_val, blue)

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
            target_val = self.get_zwave_value(
                "targetColor", property_key_name="Warm White"
            )
            await self.info.node.async_set_value(target_val, warm)
            target_val = self.get_zwave_value(
                "targetColor", property_key_name="Cold White"
            )
            await self.info.node.async_set_value(target_val, cold)

        # White value
        white = kwargs.get(ATTR_WHITE_VALUE)
        if white and self._supports_white_value:
            target_val = self.get_zwave_value(
                "targetColor", property_key_name="Warm White"
            )
            await self.info.node.async_set_value(target_val, warm)

        # set brightness
        await self._async_set_brightness(
            kwargs.get(ATTR_BRIGHTNESS), kwargs.get(ATTR_TRANSITION)
        )

    async def async_turn_off(self, **kwargs: dict) -> Optional[int]:
        """Turn the light off."""
        await self._async_set_brightness(0, kwargs.get(ATTR_TRANSITION))

    async def _async_set_brightness(
        self, brightness: Optional[int], transition: Optional[int] = None
    ) -> None:
        """Set new brightness to light."""
        await self._async_set_transition_duration(transition)
        # Zwave multilevel switches use a range of [0, 99] to control
        # brightness. Level 255 means to set it to previous value.
        if brightness is None:
            brightness = 255
        else:
            brightness = byte_to_zwave_brightness(brightness)
        if self._target_value is not None:
            await self.info.node.async_set_value(self._target_value, brightness)
        else:
            await self.info.node.async_set_value(self.info.primary_value, brightness)

    async def _async_set_transition_duration(
        self, duration: Optional[int] = None
    ) -> None:
        """Set the transition time for the brightness value."""
        if self._dimming_duration is None:
            return

        # TODO: setting duration needs to be fixed upstream
        # https://github.com/zwave-js/node-zwave-js/issues/1321
        return

        if duration is None:
            # no transition specified by user, use defaults
            duration = 7621  # anything over 7620 uses the factory default
        else:
            # transition specified by user
            transition = duration
            if transition <= 127:
                duration = int(transition)
            else:
                minutes = int(transition / 60)
                LOGGER.debug(
                    "Transition rounded to %d minutes for %s",
                    minutes,
                    self.entity_id,
                )
                duration = minutes + 128

        # only send value if it differs from current
        # this prevents sending a command for nothing
        if self._dimming_duration.value != duration:
            await self.info.node.async_set_value(self._dimming_duration, duration)

    @callback
    def _calculate_color_values(self) -> None:
        """Calculate light colors."""

        # RGB support
        red_val = self.get_zwave_value(
            "currentColor", CommandClass.SWITCH_COLOR, property_key_name="Red"
        )
        green_val = self.get_zwave_value(
            "currentColor", CommandClass.SWITCH_COLOR, property_key_name="Green"
        )
        blue_val = self.get_zwave_value(
            "currentColor", CommandClass.SWITCH_COLOR, property_key_name="Blue"
        )
        if red_val and green_val and blue_val:
            self._supports_color = True
            # convert to HS
            self._hs = color_util.color_RGB_to_hs(
                red_val.value, green_val.value, blue_val.value
            )

        # Update color temp limits.
        min_kelvin_val = self.get_zwave_value(81, CommandClass.CONFIGURATION)
        if min_kelvin_val:
            self._max_mireds = color_util.color_temperature_kelvin_to_mired(
                min_kelvin_val.value
            )
        max_kelvin_val = self.get_zwave_value(82, CommandClass.CONFIGURATION)
        if max_kelvin_val:
            self._min_mireds = color_util.color_temperature_kelvin_to_mired(
                max_kelvin_val.value
            )

        # White colors
        ww_val = self.get_zwave_value(
            "currentColor", CommandClass.SWITCH_COLOR, property_key_name="Warm White"
        )
        cw_val = self.get_zwave_value(
            "currentColor", CommandClass.SWITCH_COLOR, property_key_name="Cold White"
        )
        if ww_val and cw_val:
            # Color temperature (CW + WW) Support
            self._supports_color_temp = True
            # Calculate color temps based on whites
            if cw_val.value or ww_val.value:
                self._color_temp = round(
                    self._max_mireds
                    - ((cw_val.value / 255) * (self._max_mireds - self._min_mireds))
                )
            else:
                self._color_temp = None
        elif ww_val or cw_val:
            # only one white channel
            self._supports_white_value = True
