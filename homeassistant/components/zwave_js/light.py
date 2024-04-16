"""Support for Z-Wave lights."""

from __future__ import annotations

from typing import Any, cast

from zwave_js_server.client import Client as ZwaveClient
from zwave_js_server.const import (
    TARGET_VALUE_PROPERTY,
    TRANSITION_DURATION_OPTION,
    CommandClass,
)
from zwave_js_server.const.command_class.color_switch import (
    COLOR_SWITCH_COMBINED_AMBER,
    COLOR_SWITCH_COMBINED_BLUE,
    COLOR_SWITCH_COMBINED_COLD_WHITE,
    COLOR_SWITCH_COMBINED_CYAN,
    COLOR_SWITCH_COMBINED_GREEN,
    COLOR_SWITCH_COMBINED_PURPLE,
    COLOR_SWITCH_COMBINED_RED,
    COLOR_SWITCH_COMBINED_WARM_WHITE,
    CURRENT_COLOR_PROPERTY,
    TARGET_COLOR_PROPERTY,
    ColorComponent,
)
from zwave_js_server.const.command_class.multilevel_switch import SET_TO_PREVIOUS_VALUE
from zwave_js_server.model.driver import Driver
from zwave_js_server.model.value import Value

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .const import DATA_CLIENT, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

PARALLEL_UPDATES = 0

MULTI_COLOR_MAP = {
    ColorComponent.WARM_WHITE: COLOR_SWITCH_COMBINED_WARM_WHITE,
    ColorComponent.COLD_WHITE: COLOR_SWITCH_COMBINED_COLD_WHITE,
    ColorComponent.RED: COLOR_SWITCH_COMBINED_RED,
    ColorComponent.GREEN: COLOR_SWITCH_COMBINED_GREEN,
    ColorComponent.BLUE: COLOR_SWITCH_COMBINED_BLUE,
    ColorComponent.AMBER: COLOR_SWITCH_COMBINED_AMBER,
    ColorComponent.CYAN: COLOR_SWITCH_COMBINED_CYAN,
    ColorComponent.PURPLE: COLOR_SWITCH_COMBINED_PURPLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Wave Light from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_light(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Light."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.

        if info.platform_hint == "black_is_off":
            async_add_entities([ZwaveBlackIsOffLight(config_entry, driver, info)])
        else:
            async_add_entities([ZwaveLight(config_entry, driver, info)])

    config_entry.async_on_unload(
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
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the light."""
        super().__init__(config_entry, driver, info)
        self._supports_color = False
        self._supports_rgbw = False
        self._supports_color_temp = False
        self._hs_color: tuple[float, float] | None = None
        self._rgbw_color: tuple[int, int, int, int] | None = None
        self._color_mode: str | None = None
        self._color_temp: int | None = None
        self._min_mireds = 153  # 6500K as a safe default
        self._max_mireds = 370  # 2700K as a safe default
        self._warm_white = self.get_zwave_value(
            TARGET_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.WARM_WHITE,
        )
        self._cold_white = self.get_zwave_value(
            TARGET_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.COLD_WHITE,
        )
        self._supported_color_modes: set[ColorMode] = set()

        # get additional (optional) values and set features
        # If the command class is Basic, we must geenerate a name that includes
        # the command class name to avoid ambiguity
        self._target_brightness = self.get_zwave_value(
            TARGET_VALUE_PROPERTY,
            CommandClass.SWITCH_MULTILEVEL,
            add_to_watched_value_ids=False,
        )
        if self.info.primary_value.command_class == CommandClass.BASIC:
            self._attr_name = self.generate_name(
                include_value_name=True, alternate_value_name="Basic"
            )
            self._target_brightness = self.get_zwave_value(
                TARGET_VALUE_PROPERTY,
                CommandClass.BASIC,
                add_to_watched_value_ids=False,
            )
        self._target_color = self.get_zwave_value(
            TARGET_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            add_to_watched_value_ids=False,
        )

        self._calculate_color_support()
        if self._supports_rgbw:
            self._supported_color_modes.add(ColorMode.RGBW)
        elif self._supports_color:
            self._supported_color_modes.add(ColorMode.HS)
        if self._supports_color_temp:
            self._supported_color_modes.add(ColorMode.COLOR_TEMP)
        if not self._supported_color_modes:
            self._supported_color_modes.add(ColorMode.BRIGHTNESS)
        self._calculate_color_values()

        # Entity class attributes
        self.supports_brightness_transition = bool(
            self._target_brightness is not None
            and TRANSITION_DURATION_OPTION
            in self._target_brightness.metadata.value_change_options
        )
        self.supports_color_transition = bool(
            self._target_color is not None
            and TRANSITION_DURATION_OPTION
            in self._target_color.metadata.value_change_options
        )

        if self.supports_brightness_transition or self.supports_color_transition:
            self._attr_supported_features |= LightEntityFeature.TRANSITION

        self._set_optimistic_state: bool = False

    @callback
    def on_value_update(self) -> None:
        """Call when a watched value is added or updated."""
        self._calculate_color_values()

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255.

        Z-Wave multilevel switches use a range of [0, 99] to control brightness.
        """
        if self.info.primary_value.value is None:
            return None
        return round((cast(int, self.info.primary_value.value) / 99) * 255)

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        return self._color_mode

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on (brightness above 0)."""
        if self._set_optimistic_state:
            self._set_optimistic_state = False
            return True
        brightness = self.brightness
        return brightness > 0 if brightness is not None else None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs color."""
        return self._hs_color

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the hs color."""
        return self._rgbw_color

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
    def supported_color_modes(self) -> set[ColorMode] | None:
        """Flag supported features."""
        return self._supported_color_modes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""

        transition = kwargs.get(ATTR_TRANSITION)

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
            await self._async_set_colors(colors, transition)

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
                },
                transition,
            )

        # RGBW
        rgbw = kwargs.get(ATTR_RGBW_COLOR)
        if rgbw is not None and self._supports_rgbw:
            rgbw_channels = {
                ColorComponent.RED: rgbw[0],
                ColorComponent.GREEN: rgbw[1],
                ColorComponent.BLUE: rgbw[2],
            }
            if self._warm_white:
                rgbw_channels[ColorComponent.WARM_WHITE] = rgbw[3]

            if self._cold_white:
                rgbw_channels[ColorComponent.COLD_WHITE] = rgbw[3]
            await self._async_set_colors(rgbw_channels, transition)

        # set brightness
        await self._async_set_brightness(kwargs.get(ATTR_BRIGHTNESS), transition)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._async_set_brightness(0, kwargs.get(ATTR_TRANSITION))

    async def _async_set_colors(
        self, colors: dict[ColorComponent, int], transition: float | None = None
    ) -> None:
        """Set (multiple) defined colors to given value(s)."""
        # prefer the (new) combined color property
        # https://github.com/zwave-js/node-zwave-js/pull/1782
        # Setting colors is only done if there's a target color value.
        combined_color_val = cast(
            Value,
            self.get_zwave_value(
                "targetColor",
                CommandClass.SWITCH_COLOR,
                value_property_key=None,
            ),
        )
        zwave_transition = None

        if self.supports_color_transition:
            if transition is not None:
                zwave_transition = {TRANSITION_DURATION_OPTION: f"{int(transition)}s"}
            else:
                zwave_transition = {TRANSITION_DURATION_OPTION: "default"}

        colors_dict = {}
        for color, value in colors.items():
            color_name = MULTI_COLOR_MAP[color]
            colors_dict[color_name] = value
        # set updated color object
        await self._async_set_value(combined_color_val, colors_dict, zwave_transition)

    async def _async_set_brightness(
        self, brightness: int | None, transition: float | None = None
    ) -> None:
        """Set new brightness to light."""
        # If we have no target brightness value, there is nothing to do
        if not self._target_brightness:
            return
        if brightness is None:
            zwave_brightness = SET_TO_PREVIOUS_VALUE
        else:
            # Zwave multilevel switches use a range of [0, 99] to control brightness.
            zwave_brightness = byte_to_zwave_brightness(brightness)

        # set transition value before sending new brightness
        zwave_transition = None
        if self.supports_brightness_transition:
            if transition is not None:
                zwave_transition = {TRANSITION_DURATION_OPTION: f"{int(transition)}s"}
            else:
                zwave_transition = {TRANSITION_DURATION_OPTION: "default"}

        # setting a value requires setting targetValue
        await self._async_set_value(
            self._target_brightness, zwave_brightness, zwave_transition
        )
        # We do an optimistic state update when setting to a previous value
        # to avoid waiting for the value to be updated from the device which is
        # typically delayed and causes a confusing UX.
        if (
            zwave_brightness == SET_TO_PREVIOUS_VALUE
            and self.info.primary_value.command_class
            in (CommandClass.BASIC, CommandClass.SWITCH_MULTILEVEL)
        ):
            self._set_optimistic_state = True
            self.async_write_ha_state()

    @callback
    def _get_color_values(self) -> tuple[Value | None, ...]:
        """Get light colors."""
        # NOTE: We lookup all values here (instead of relying on the multicolor one)
        # to find out what colors are supported
        # as this is a simple lookup by key, this not heavy
        red_val = self.get_zwave_value(
            CURRENT_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.RED.value,
        )
        green_val = self.get_zwave_value(
            CURRENT_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.GREEN.value,
        )
        blue_val = self.get_zwave_value(
            CURRENT_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.BLUE.value,
        )
        ww_val = self.get_zwave_value(
            CURRENT_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.WARM_WHITE.value,
        )
        cw_val = self.get_zwave_value(
            CURRENT_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            value_property_key=ColorComponent.COLD_WHITE.value,
        )
        return (red_val, green_val, blue_val, ww_val, cw_val)

    @callback
    def _calculate_color_support(self) -> None:
        """Calculate light colors."""
        (red, green, blue, warm_white, cool_white) = self._get_color_values()
        # RGB support
        if red and green and blue:
            self._supports_color = True
        # color temperature support
        if warm_white and cool_white:
            self._supports_color_temp = True
        # only one white channel (warm white or cool white) = rgbw support
        elif red and green and blue and warm_white or cool_white:
            self._supports_rgbw = True

    @callback
    def _calculate_color_values(self) -> None:
        """Calculate light colors."""
        (red_val, green_val, blue_val, ww_val, cw_val) = self._get_color_values()

        # prefer the (new) combined color property
        # https://github.com/zwave-js/node-zwave-js/pull/1782
        combined_color_val = self.get_zwave_value(
            CURRENT_COLOR_PROPERTY,
            CommandClass.SWITCH_COLOR,
            value_property_key=None,
        )
        if combined_color_val and isinstance(combined_color_val.value, dict):
            multi_color = combined_color_val.value
        else:
            multi_color = {}

        # Default: Brightness (no color) or Unknown
        if self.supported_color_modes == {ColorMode.BRIGHTNESS}:
            self._color_mode = ColorMode.BRIGHTNESS
        else:
            self._color_mode = ColorMode.UNKNOWN

        # RGB support
        if red_val and green_val and blue_val:
            # prefer values from the multicolor property
            red = multi_color.get(COLOR_SWITCH_COMBINED_RED, red_val.value)
            green = multi_color.get(COLOR_SWITCH_COMBINED_GREEN, green_val.value)
            blue = multi_color.get(COLOR_SWITCH_COMBINED_BLUE, blue_val.value)
            if None not in (red, green, blue):
                # convert to HS
                self._hs_color = color_util.color_RGB_to_hs(red, green, blue)
                # Light supports color, set color mode to hs
                self._color_mode = ColorMode.HS

        # color temperature support
        if ww_val and cw_val:
            warm_white = multi_color.get(COLOR_SWITCH_COMBINED_WARM_WHITE, ww_val.value)
            cold_white = multi_color.get(COLOR_SWITCH_COMBINED_COLD_WHITE, cw_val.value)
            # Calculate color temps based on whites
            if cold_white or warm_white:
                self._color_temp = round(
                    self._max_mireds
                    - ((cold_white / 255) * (self._max_mireds - self._min_mireds))
                )
                # White channels turned on, set color mode to color_temp
                self._color_mode = ColorMode.COLOR_TEMP
            else:
                self._color_temp = None
        # only one white channel (warm white) = rgbw support
        elif red_val and green_val and blue_val and ww_val:
            white = multi_color.get(COLOR_SWITCH_COMBINED_WARM_WHITE, ww_val.value)
            self._rgbw_color = (red, green, blue, white)
            # Light supports rgbw, set color mode to rgbw
            self._color_mode = ColorMode.RGBW
        # only one white channel (cool white) = rgbw support
        elif cw_val:
            self._supports_rgbw = True
            white = multi_color.get(COLOR_SWITCH_COMBINED_COLD_WHITE, cw_val.value)
            self._rgbw_color = (red, green, blue, white)
            # Light supports rgbw, set color mode to rgbw
            self._color_mode = ColorMode.RGBW


class ZwaveBlackIsOffLight(ZwaveLight):
    """Representation of a Z-Wave light where setting the color to black turns it off.

    Currently only supports lights with RGB, no color temperature, and no white
    channels.
    """

    def __init__(
        self, config_entry: ConfigEntry, driver: Driver, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the light."""
        super().__init__(config_entry, driver, info)

        self._last_color: dict[str, int] | None = None
        self._supported_color_modes.discard(ColorMode.BRIGHTNESS)

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return 255

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on (brightness above 0)."""
        if self.info.primary_value.value is None:
            return None
        return any(value != 0 for value in self.info.primary_value.value.values())

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if (
            kwargs.get(ATTR_RGBW_COLOR) is not None
            or kwargs.get(ATTR_COLOR_TEMP) is not None
            or kwargs.get(ATTR_HS_COLOR) is not None
        ):
            await super().async_turn_on(**kwargs)
            return

        transition = kwargs.get(ATTR_TRANSITION)
        # turn on light to last color if known, otherwise set to white
        if self._last_color is not None:
            await self._async_set_colors(
                {
                    ColorComponent.RED: self._last_color["red"],
                    ColorComponent.GREEN: self._last_color["green"],
                    ColorComponent.BLUE: self._last_color["blue"],
                },
                transition,
            )
        else:
            await self._async_set_colors(
                {
                    ColorComponent.RED: 255,
                    ColorComponent.GREEN: 255,
                    ColorComponent.BLUE: 255,
                },
                transition,
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._last_color = self.info.primary_value.value
        await self._async_set_colors(
            {
                ColorComponent.RED: 0,
                ColorComponent.GREEN: 0,
                ColorComponent.BLUE: 0,
            },
            kwargs.get(ATTR_TRANSITION),
        )
        await self._async_set_brightness(0, kwargs.get(ATTR_TRANSITION))
