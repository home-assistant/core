"""Class to hold all light accessories."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from pyhap.const import CATEGORY_LIGHTBULB

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    ATTR_WHITE,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    brightness_supported,
    color_supported,
    color_temp_supported,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import CALLBACK_TYPE, State, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
    color_temperature_to_hs,
    color_temperature_to_rgbww,
)

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_BRIGHTNESS,
    CHAR_COLOR_TEMPERATURE,
    CHAR_HUE,
    CHAR_ON,
    CHAR_SATURATION,
    PROP_MAX_VALUE,
    PROP_MIN_VALUE,
    SERV_LIGHTBULB,
)
from .util import get_min_max

_LOGGER = logging.getLogger(__name__)


CHANGE_COALESCE_TIME_WINDOW = 0.01

DEFAULT_MIN_COLOR_TEMP = 2000  # 500 mireds
DEFAULT_MAX_COLOR_TEMP = 6500  # 153 mireds

COLOR_MODES_WITH_WHITES = {ColorMode.RGBW, ColorMode.RGBWW, ColorMode.WHITE}


@TYPES.register("Light")
class Light(HomeAccessory):
    """Generate a Light accessory for a light entity.

    Currently supports: state, brightness, color temperature, rgb_color.
    """

    def __init__(self, *args: Any) -> None:
        """Initialize a new Light accessory object."""
        super().__init__(*args, category=CATEGORY_LIGHTBULB)
        self._reload_on_change_attrs.extend(
            (
                ATTR_SUPPORTED_COLOR_MODES,
                ATTR_MAX_COLOR_TEMP_KELVIN,
                ATTR_MIN_COLOR_TEMP_KELVIN,
            )
        )
        self.chars = []
        self._event_timer: CALLBACK_TYPE | None = None
        self._pending_events: dict[str, Any] = {}

        state = self.hass.states.get(self.entity_id)
        assert state
        attributes = state.attributes
        self.color_modes = color_modes = (
            attributes.get(ATTR_SUPPORTED_COLOR_MODES) or []
        )
        self._previous_color_mode = attributes.get(ATTR_COLOR_MODE)
        self.color_supported = color_supported(color_modes)
        self.color_temp_supported = color_temp_supported(color_modes)
        self.rgbw_supported = ColorMode.RGBW in color_modes
        self.rgbww_supported = ColorMode.RGBWW in color_modes
        self.white_supported = ColorMode.WHITE in color_modes
        self.brightness_supported = brightness_supported(color_modes)

        if self.brightness_supported:
            self.chars.append(CHAR_BRIGHTNESS)

        if self.color_supported:
            self.chars.extend([CHAR_HUE, CHAR_SATURATION])

        if self.color_temp_supported or COLOR_MODES_WITH_WHITES.intersection(
            self.color_modes
        ):
            self.chars.append(CHAR_COLOR_TEMPERATURE)

        serv_light = self.add_preload_service(SERV_LIGHTBULB, self.chars)
        self.char_on = serv_light.configure_char(CHAR_ON, value=0)

        if self.brightness_supported:
            # Initial value is set to 100 because 0 is a special value (off). 100 is
            # an arbitrary non-zero value. It is updated immediately by async_update_state
            # to set to the correct initial value.
            self.char_brightness = serv_light.configure_char(CHAR_BRIGHTNESS, value=100)

        if CHAR_COLOR_TEMPERATURE in self.chars:
            min_mireds = color_temperature_kelvin_to_mired(
                attributes.get(ATTR_MAX_COLOR_TEMP_KELVIN, DEFAULT_MAX_COLOR_TEMP)
            )
            max_mireds = color_temperature_kelvin_to_mired(
                attributes.get(ATTR_MIN_COLOR_TEMP_KELVIN, DEFAULT_MIN_COLOR_TEMP)
            )
            # Ensure min is less than max
            self.min_mireds, self.max_mireds = get_min_max(min_mireds, max_mireds)
            if not self.color_temp_supported and not self.rgbww_supported:
                self.max_mireds = self.min_mireds
            self.char_color_temp = serv_light.configure_char(
                CHAR_COLOR_TEMPERATURE,
                value=self.min_mireds,
                properties={
                    PROP_MIN_VALUE: self.min_mireds,
                    PROP_MAX_VALUE: self.max_mireds,
                },
            )

        if self.color_supported:
            self.char_hue = serv_light.configure_char(CHAR_HUE, value=0)
            self.char_saturation = serv_light.configure_char(CHAR_SATURATION, value=75)

        self.async_update_state(state)
        serv_light.setter_callback = self._set_chars

    def _set_chars(self, char_values: dict[str, Any]) -> None:
        _LOGGER.debug("Light _set_chars: %s", char_values)
        # Newest change always wins
        if CHAR_COLOR_TEMPERATURE in self._pending_events and (
            CHAR_SATURATION in char_values or CHAR_HUE in char_values
        ):
            del self._pending_events[CHAR_COLOR_TEMPERATURE]
        for char in (CHAR_HUE, CHAR_SATURATION):
            if char in self._pending_events and CHAR_COLOR_TEMPERATURE in char_values:
                del self._pending_events[char]

        self._pending_events.update(char_values)
        if self._event_timer:
            self._event_timer()
        self._event_timer = async_call_later(
            self.hass, CHANGE_COALESCE_TIME_WINDOW, self._async_send_events
        )

    @callback
    def _async_send_events(self, _now: datetime) -> None:
        """Process all changes at once."""
        _LOGGER.debug("Coalesced _set_chars: %s", self._pending_events)
        char_values = self._pending_events
        self._pending_events = {}
        events = []
        service = SERVICE_TURN_ON
        params: dict[str, Any] = {ATTR_ENTITY_ID: self.entity_id}
        has_on = CHAR_ON in char_values

        if has_on:
            if not char_values[CHAR_ON]:
                service = SERVICE_TURN_OFF
            events.append(f"Set state to {char_values[CHAR_ON]}")

        brightness_pct = None
        if CHAR_BRIGHTNESS in char_values:
            if char_values[CHAR_BRIGHTNESS] == 0:
                if has_on:
                    events[-1] = "Set state to 0"
                else:
                    events.append("Set state to 0")
                service = SERVICE_TURN_OFF
            else:
                brightness_pct = char_values[CHAR_BRIGHTNESS]
            events.append(f"brightness at {char_values[CHAR_BRIGHTNESS]}%")

        if service == SERVICE_TURN_OFF:
            self.async_call_service(
                LIGHT_DOMAIN,
                service,
                {ATTR_ENTITY_ID: self.entity_id},
                ", ".join(events),
            )
            return

        # Handle white channels
        if CHAR_COLOR_TEMPERATURE in char_values:
            temp = char_values[CHAR_COLOR_TEMPERATURE]
            events.append(f"color temperature at {temp}")
            bright_val = round(
                ((brightness_pct or self.char_brightness.value) * 255) / 100
            )
            if self.color_temp_supported:
                params[ATTR_COLOR_TEMP_KELVIN] = color_temperature_mired_to_kelvin(temp)
            elif self.rgbww_supported:
                params[ATTR_RGBWW_COLOR] = color_temperature_to_rgbww(
                    color_temperature_mired_to_kelvin(temp),
                    bright_val,
                    color_temperature_mired_to_kelvin(self.max_mireds),
                    color_temperature_mired_to_kelvin(self.min_mireds),
                )
            elif self.rgbw_supported:
                params[ATTR_RGBW_COLOR] = (*(0,) * 3, bright_val)
            elif self.white_supported:
                params[ATTR_WHITE] = bright_val

        elif CHAR_HUE in char_values or CHAR_SATURATION in char_values:
            hue_sat = (
                char_values.get(CHAR_HUE, self.char_hue.value),
                char_values.get(CHAR_SATURATION, self.char_saturation.value),
            )
            _LOGGER.debug("%s: Set hs_color to %s", self.entity_id, hue_sat)
            events.append(f"set color at {hue_sat}")
            params[ATTR_HS_COLOR] = hue_sat

        if (
            brightness_pct
            and ATTR_RGBWW_COLOR not in params
            and ATTR_RGBW_COLOR not in params
        ):
            params[ATTR_BRIGHTNESS_PCT] = brightness_pct

        _LOGGER.debug(
            "Calling light service with params: %s -> %s", char_values, params
        )
        self.async_call_service(LIGHT_DOMAIN, service, params, ", ".join(events))

    @callback
    def async_update_state(self, new_state: State) -> None:
        """Update light after state change."""
        # Handle State
        state = new_state.state
        attributes = new_state.attributes
        color_mode = attributes.get(ATTR_COLOR_MODE)
        self.char_on.set_value(int(state == STATE_ON))
        color_mode_changed = self._previous_color_mode != color_mode
        self._previous_color_mode = color_mode

        # Handle Brightness
        if (
            self.brightness_supported
            and (brightness := attributes.get(ATTR_BRIGHTNESS)) is not None
            and isinstance(brightness, (int, float))
        ):
            brightness = round(brightness / 255 * 100, 0)
            # The homeassistant component might report its brightness as 0 but is
            # not off. But 0 is a special value in homekit. When you turn on a
            # homekit accessory it will try to restore the last brightness state
            # which will be the last value saved by char_brightness.set_value.
            # But if it is set to 0, HomeKit will update the brightness to 100 as
            # it thinks 0 is off.
            #
            # Therefore, if the brightness is 0 and the device is still on,
            # the brightness is mapped to 1 otherwise the update is ignored in
            # order to avoid this incorrect behavior.
            if brightness == 0 and state == STATE_ON:
                brightness = 1
            self.char_brightness.set_value(brightness)
            if color_mode_changed:
                self.char_brightness.notify()

        # Handle Color - color must always be set before color temperature
        # or the iOS UI will not display it correctly.
        if self.color_supported:
            if color_temp := attributes.get(ATTR_COLOR_TEMP_KELVIN):
                hue, saturation = color_temperature_to_hs(color_temp)
            elif color_mode == ColorMode.WHITE:
                hue, saturation = 0, 0
            elif (
                (hue_sat := attributes.get(ATTR_HS_COLOR))
                and isinstance(hue_sat, (list, tuple))
                and len(hue_sat) == 2
            ):
                hue, saturation = hue_sat
            else:
                hue = None
                saturation = None
            if isinstance(hue, (int, float)) and isinstance(saturation, (int, float)):
                self.char_hue.set_value(round(hue, 0))
                self.char_saturation.set_value(round(saturation, 0))
                if color_mode_changed:
                    # If the color temp changed, be sure to force the color to update
                    self.char_hue.notify()
                    self.char_saturation.notify()

        # Handle white channels
        if CHAR_COLOR_TEMPERATURE in self.chars:
            color_temp = None
            if self.color_temp_supported:
                color_temp_kelvin = attributes.get(ATTR_COLOR_TEMP_KELVIN)
                if color_temp_kelvin is not None:
                    color_temp = color_temperature_kelvin_to_mired(color_temp_kelvin)
            elif color_mode == ColorMode.WHITE:
                color_temp = self.min_mireds
            if isinstance(color_temp, (int, float)):
                self.char_color_temp.set_value(round(color_temp, 0))
                if color_mode_changed:
                    self.char_color_temp.notify()
