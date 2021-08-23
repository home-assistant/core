"""Class to hold all light accessories."""
import logging
import math

from pyhap.const import CATEGORY_LIGHTBULB

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_SUPPORTED_COLOR_MODES,
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
from homeassistant.helpers.event import async_call_later
from homeassistant.util.color import (
    color_temperature_mired_to_kelvin,
    color_temperature_to_hs,
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

_LOGGER = logging.getLogger(__name__)

RGB_COLOR = "rgb_color"

CHANGE_COALESCE_TIME_WINDOW = 0.01


@TYPES.register("Light")
class Light(HomeAccessory):
    """Generate a Light accessory for a light entity.

    Currently supports: state, brightness, color temperature, rgb_color.
    """

    def __init__(self, *args):
        """Initialize a new Light accessory object."""
        super().__init__(*args, category=CATEGORY_LIGHTBULB)

        self.chars = []
        self._event_timer = None
        self._pending_events = {}

        state = self.hass.states.get(self.entity_id)
        attributes = state.attributes
        color_modes = attributes.get(ATTR_SUPPORTED_COLOR_MODES)
        self.color_supported = color_supported(color_modes)
        self.color_temp_supported = color_temp_supported(color_modes)
        self.brightness_supported = brightness_supported(color_modes)

        if self.brightness_supported:
            self.chars.append(CHAR_BRIGHTNESS)

        if self.color_supported:
            self.chars.extend([CHAR_HUE, CHAR_SATURATION])

        if self.color_temp_supported:
            self.chars.append(CHAR_COLOR_TEMPERATURE)

        serv_light = self.add_preload_service(SERV_LIGHTBULB, self.chars)
        self.char_on = serv_light.configure_char(CHAR_ON, value=0)

        if self.brightness_supported:
            # Initial value is set to 100 because 0 is a special value (off). 100 is
            # an arbitrary non-zero value. It is updated immediately by async_update_state
            # to set to the correct initial value.
            self.char_brightness = serv_light.configure_char(CHAR_BRIGHTNESS, value=100)

        if self.color_temp_supported:
            min_mireds = math.floor(attributes.get(ATTR_MIN_MIREDS, 153))
            max_mireds = math.ceil(attributes.get(ATTR_MAX_MIREDS, 500))
            self.char_color_temp = serv_light.configure_char(
                CHAR_COLOR_TEMPERATURE,
                value=min_mireds,
                properties={PROP_MIN_VALUE: min_mireds, PROP_MAX_VALUE: max_mireds},
            )

        if self.color_supported:
            self.char_hue = serv_light.configure_char(CHAR_HUE, value=0)
            self.char_saturation = serv_light.configure_char(CHAR_SATURATION, value=75)

        self.async_update_state(state)
        serv_light.setter_callback = self._set_chars

    def _set_chars(self, char_values):
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
            self.hass, CHANGE_COALESCE_TIME_WINDOW, self._send_events
        )

    def _send_events(self, *_):
        """Process all changes at once."""
        _LOGGER.debug("Coalesced _set_chars: %s", self._pending_events)
        char_values = self._pending_events
        self._pending_events = {}
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

        if CHAR_COLOR_TEMPERATURE in char_values:
            params[ATTR_COLOR_TEMP] = char_values[CHAR_COLOR_TEMPERATURE]
            events.append(f"color temperature at {params[ATTR_COLOR_TEMP]}")

        elif CHAR_HUE in char_values or CHAR_SATURATION in char_values:
            color = params[ATTR_HS_COLOR] = (
                char_values.get(CHAR_HUE, self.char_hue.value),
                char_values.get(CHAR_SATURATION, self.char_saturation.value),
            )
            _LOGGER.debug("%s: Set hs_color to %s", self.entity_id, color)
            events.append(f"set color at {color}")

        self.async_call_service(DOMAIN, service, params, ", ".join(events))

    @callback
    def async_update_state(self, new_state):
        """Update light after state change."""
        # Handle State
        state = new_state.state
        attributes = new_state.attributes
        self.char_on.set_value(int(state == STATE_ON))

        # Handle Brightness
        if self.brightness_supported:
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
                self.char_brightness.set_value(brightness)

        # Handle Color - color must always be set before color temperature
        # or the iOS UI will not display it correctly.
        if self.color_supported:
            if ATTR_COLOR_TEMP in attributes:
                hue, saturation = color_temperature_to_hs(
                    color_temperature_mired_to_kelvin(
                        new_state.attributes[ATTR_COLOR_TEMP]
                    )
                )
            else:
                hue, saturation = attributes.get(ATTR_HS_COLOR, (None, None))
            if isinstance(hue, (int, float)) and isinstance(saturation, (int, float)):
                self.char_hue.set_value(round(hue, 0))
                self.char_saturation.set_value(round(saturation, 0))

        # Handle color temperature
        if self.color_temp_supported:
            color_temp = attributes.get(ATTR_COLOR_TEMP)
            if isinstance(color_temp, (int, float)):
                self.char_color_temp.set_value(round(color_temp, 0))
