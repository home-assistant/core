"""Class to hold all light accessories."""
import logging
import math

from pyhap.const import CATEGORY_LIGHTBULB

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_MODE,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_SUPPORTED_COLOR_MODES,
    COLOR_MODE_COLOR_TEMP,
    DOMAIN,
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
from homeassistant.core import callback

from .accessories import TYPES, HomeAccessory
from .const import (
    CHAR_BRIGHTNESS,
    CHAR_COLOR_TEMPERATURE,
    CHAR_HUE,
    CHAR_NAME,
    CHAR_ON,
    CHAR_SATURATION,
    PROP_MAX_VALUE,
    PROP_MIN_VALUE,
    SERV_LIGHTBULB,
)

_LOGGER = logging.getLogger(__name__)

RGB_COLOR = "rgb_color"


@TYPES.register("Light")
class Light(HomeAccessory):
    """Generate a Light accessory for a light entity.

    Currently supports: state, brightness, color temperature, rgb_color.
    """

    def __init__(self, *args):
        """Initialize a new Light accessory object."""
        super().__init__(*args, category=CATEGORY_LIGHTBULB)

        self.chars_primary = []
        self.chars_secondary = []

        state = self.hass.states.get(self.entity_id)
        attributes = state.attributes
        color_modes = attributes.get(ATTR_SUPPORTED_COLOR_MODES)
        self.is_color_supported = color_supported(color_modes)
        self.is_color_temp_supported = color_temp_supported(color_modes)
        self.color_and_temp_supported = (
            self.is_color_supported and self.is_color_temp_supported
        )
        self.is_brightness_supported = brightness_supported(color_modes)

        if self.is_brightness_supported:
            self.chars_primary.append(CHAR_BRIGHTNESS)

        if self.is_color_supported:
            self.chars_primary.append(CHAR_HUE)
            self.chars_primary.append(CHAR_SATURATION)

        if self.is_color_temp_supported:
            if self.color_and_temp_supported:
                self.chars_primary.append(CHAR_NAME)
                self.chars_secondary.append(CHAR_NAME)
                self.chars_secondary.append(CHAR_COLOR_TEMPERATURE)
                if self.is_brightness_supported:
                    self.chars_secondary.append(CHAR_BRIGHTNESS)
            else:
                self.chars_primary.append(CHAR_COLOR_TEMPERATURE)

        serv_light_primary = self.add_preload_service(
            SERV_LIGHTBULB, self.chars_primary
        )
        serv_light_secondary = None
        self.char_on_primary = serv_light_primary.configure_char(CHAR_ON, value=0)

        if self.color_and_temp_supported:
            serv_light_secondary = self.add_preload_service(
                SERV_LIGHTBULB, self.chars_secondary
            )
            serv_light_primary.add_linked_service(serv_light_secondary)
            serv_light_primary.configure_char(CHAR_NAME, value="RGB")
            self.char_on_secondary = serv_light_secondary.configure_char(
                CHAR_ON, value=0
            )
            serv_light_secondary.configure_char(CHAR_NAME, value="Temperature")

        if self.is_brightness_supported:
            # Initial value is set to 100 because 0 is a special value (off). 100 is
            # an arbitrary non-zero value. It is updated immediately by async_update_state
            # to set to the correct initial value.
            self.char_brightness_primary = serv_light_primary.configure_char(
                CHAR_BRIGHTNESS, value=100
            )
            if self.chars_secondary:
                self.char_brightness_secondary = serv_light_secondary.configure_char(
                    CHAR_BRIGHTNESS, value=100
                )

        if self.is_color_temp_supported:
            min_mireds = math.floor(attributes.get(ATTR_MIN_MIREDS, 153))
            max_mireds = math.ceil(attributes.get(ATTR_MAX_MIREDS, 500))
            serv_light = serv_light_secondary or serv_light_primary
            self.char_color_temperature = serv_light.configure_char(
                CHAR_COLOR_TEMPERATURE,
                value=min_mireds,
                properties={PROP_MIN_VALUE: min_mireds, PROP_MAX_VALUE: max_mireds},
            )

        if self.is_color_supported:
            self.char_hue = serv_light_primary.configure_char(CHAR_HUE, value=0)
            self.char_saturation = serv_light_primary.configure_char(
                CHAR_SATURATION, value=75
            )

        self.async_update_state(state)

        if self.color_and_temp_supported:
            serv_light_primary.setter_callback = self._set_chars_primary
            serv_light_secondary.setter_callback = self._set_chars_secondary
        else:
            serv_light_primary.setter_callback = self._set_chars

    def _set_chars_primary(self, char_values):
        """Primary service is RGB or W if only color or color temp is supported."""
        self._set_chars(char_values, True)

    def _set_chars_secondary(self, char_values):
        """Secondary service is W if both color or color temp are supported."""
        self._set_chars(char_values, False)

    def _set_chars(self, char_values, is_primary=None):
        _LOGGER.debug("Light _set_chars: %s, is_primary: %s", char_values, is_primary)
        events = []
        service = SERVICE_TURN_ON
        params = {ATTR_ENTITY_ID: self.entity_id}
        if CHAR_ON in char_values:
            if not char_values[CHAR_ON]:
                service = SERVICE_TURN_OFF
            events.append(f"Set state to {char_values[CHAR_ON]}")

        if CHAR_BRIGHTNESS in char_values:
            if char_values[CHAR_BRIGHTNESS] == 0:
                events[-1] = "Set state to 0"
                service = SERVICE_TURN_OFF
            else:
                params[ATTR_BRIGHTNESS_PCT] = char_values[CHAR_BRIGHTNESS]
            events.append(f"brightness at {char_values[CHAR_BRIGHTNESS]}%")

        if service == SERVICE_TURN_OFF:
            self.async_call_service(
                DOMAIN, service, {ATTR_ENTITY_ID: self.entity_id}, ", ".join(events)
            )
            return

        if self.is_color_temp_supported and (
            is_primary is False or CHAR_COLOR_TEMPERATURE in char_values
        ):
            params[ATTR_COLOR_TEMP] = char_values.get(
                CHAR_COLOR_TEMPERATURE, self.char_color_temperature.value
            )
            events.append(f"color temperature at {params[ATTR_COLOR_TEMP]}")

        if self.is_color_supported and (
            is_primary is True
            or (CHAR_HUE in char_values and CHAR_SATURATION in char_values)
        ):
            color = (
                char_values.get(CHAR_HUE, self.char_hue.value),
                char_values.get(CHAR_SATURATION, self.char_saturation.value),
            )
            _LOGGER.debug("%s: Set hs_color to %s", self.entity_id, color)
            params[ATTR_HS_COLOR] = color
            events.append(f"set color at {color}")

        self.async_call_service(DOMAIN, service, params, ", ".join(events))

    @callback
    def async_update_state(self, new_state):
        """Update light after state change."""
        # Handle State
        state = new_state.state
        attributes = new_state.attributes
        char_on_value = int(state == STATE_ON)

        if self.color_and_temp_supported:
            color_mode = attributes.get(ATTR_COLOR_MODE)
            color_temp_mode = color_mode == COLOR_MODE_COLOR_TEMP
            primary_on_value = char_on_value if not color_temp_mode else 0
            secondary_on_value = char_on_value if color_temp_mode else 0
            if self.char_on_primary.value != primary_on_value:
                self.char_on_primary.set_value(primary_on_value)
            if self.char_on_secondary.value != secondary_on_value:
                self.char_on_secondary.set_value(secondary_on_value)
        else:
            if self.char_on_primary.value != char_on_value:
                self.char_on_primary.set_value(char_on_value)

        # Handle Brightness
        if self.is_brightness_supported:
            brightness = attributes.get(ATTR_BRIGHTNESS)
            if isinstance(brightness, (int, float)):
                brightness = round(brightness / 255 * 100, 0)
                # The homeassistant component might report its brightness as 0 but is
                # not off. But 0 is a special value in homekit. When you turn on a
                # homekit accessory it will try to restore the last brightness state
                # which will be the last value saved by char_brightness.set_value.
                # But if it is set to 0, HomeKit will update the brightness to 100 as
                # it thinks 0 is off.
                #
                # Therefore, if the the brightness is 0 and the device is still on,
                # the brightness is mapped to 1 otherwise the update is ignored in
                # order to avoid this incorrect behavior.
                if brightness == 0 and state == STATE_ON:
                    brightness = 1
                if self.char_brightness_primary.value != brightness:
                    self.char_brightness_primary.set_value(brightness)
                if (
                    self.color_and_temp_supported
                    and self.char_brightness_secondary.value != brightness
                ):
                    self.char_brightness_secondary.set_value(brightness)

        # Handle color temperature
        if self.is_color_temp_supported:
            color_temperature = attributes.get(ATTR_COLOR_TEMP)
            if isinstance(color_temperature, (int, float)):
                color_temperature = round(color_temperature, 0)
                if self.char_color_temperature.value != color_temperature:
                    self.char_color_temperature.set_value(color_temperature)

        # Handle Color
        if self.is_color_supported:
            hue, saturation = attributes.get(ATTR_HS_COLOR, (None, None))
            if isinstance(hue, (int, float)) and isinstance(saturation, (int, float)):
                hue = round(hue, 0)
                saturation = round(saturation, 0)
                if hue != self.char_hue.value:
                    self.char_hue.set_value(hue)
                if saturation != self.char_saturation.value:
                    self.char_saturation.set_value(saturation)
