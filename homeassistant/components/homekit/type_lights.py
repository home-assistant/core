"""Class to hold all light accessories."""

from datetime import datetime
import logging
from typing import Any, override

from pyhap.const import CATEGORY_LIGHTBULB
from pyhap.util import callback as pyhap_callback

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
    LightEntityCapabilityAttribute,
    LightEntityStateAttribute,
    LightService,
    LightServiceArgument,
    brightness_supported,
    color_supported,
    color_temp_supported,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import CALLBACK_TYPE, State, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.util.color import (
    color_temperature_kelvin_to_mired,
    color_temperature_mired_to_kelvin,
    color_temperature_to_hs,
    color_temperature_to_rgb,
    color_temperature_to_rgbww,
)

from .accessories import TYPES, HomeAccessory
from .adaptive_lighting import (
    ADAPTIVE_LIGHTING_CHARS,
    AdaptiveLightingController,
    async_delete_stored_schedule,
)
from .const import (
    CHAR_BRIGHTNESS,
    CHAR_COLOR_TEMPERATURE,
    CHAR_HUE,
    CHAR_ON,
    CHAR_SATURATION,
    CONF_ADAPTIVE_LIGHTING,
    CONF_FLOOR_RGB_COLOR,
    CONF_MAX_COLOR_TEMP_KELVIN,
    CONF_MIN_COLOR_TEMP_KELVIN,
    CONF_RGB_BELOW_KELVIN,
    CONF_WARM_RGB_COLOR,
    PROP_MAX_VALUE,
    PROP_MIN_VALUE,
    SERV_LIGHTBULB,
)
from .util import get_min_max

_LOGGER = logging.getLogger(__name__)


CHANGE_COALESCE_TIME_WINDOW = 0.01

# Characteristics that only describe colour, never on/off intent.
COLOR_ONLY_CHARS = {CHAR_COLOR_TEMPERATURE, CHAR_HUE, CHAR_SATURATION}

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
                LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES,
                LightEntityCapabilityAttribute.MAX_COLOR_TEMP_KELVIN,
                LightEntityCapabilityAttribute.MIN_COLOR_TEMP_KELVIN,
            )
        )
        self.chars = []
        self._event_timer: CALLBACK_TYPE | None = None
        self._pending_events: dict[str, Any] = {}
        self._pending_turn_on = False

        state = self.hass.states.get(self.entity_id)
        assert state
        attributes = state.attributes
        self.color_modes = color_modes = (
            attributes.get(LightEntityCapabilityAttribute.SUPPORTED_COLOR_MODES) or []
        )
        self._previous_color_mode = attributes.get(LightEntityStateAttribute.COLOR_MODE)
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

        # Adaptive lighting transitions both brightness and colour temperature,
        # so it is only offered when the light supports both.
        self._adaptive_lighting_enabled = bool(
            self.config.get(CONF_ADAPTIVE_LIGHTING)
            and self.brightness_supported
            and CHAR_COLOR_TEMPERATURE in self.chars
        )
        if self._adaptive_lighting_enabled:
            self.chars.extend(ADAPTIVE_LIGHTING_CHARS)

        serv_light = self.add_preload_service(SERV_LIGHTBULB, self.chars)
        self.char_on = serv_light.configure_char(CHAR_ON, value=0)

        if self.brightness_supported:
            # Initial value is set to 100 because 0 is a special
            # value (off). 100 is an arbitrary non-zero value. It
            # is updated immediately by async_update_state to set
            # to the correct initial value.
            self.char_brightness = serv_light.configure_char(CHAR_BRIGHTNESS, value=100)

        if CHAR_COLOR_TEMPERATURE in self.chars:
            # Some bulbs report a wider range than the hardware accepts and go
            # dark instead of clamping, so the range can be overridden per entity.
            if max_kelvin := self.config.get(CONF_MAX_COLOR_TEMP_KELVIN):
                # The configured maximum is a ceiling: ceil keeps the mired
                # bound from converting back above it.
                min_mireds = -(-1_000_000 // max_kelvin)
            else:
                min_mireds = color_temperature_kelvin_to_mired(
                    attributes.get(
                        LightEntityCapabilityAttribute.MAX_COLOR_TEMP_KELVIN,
                        DEFAULT_MAX_COLOR_TEMP,
                    )
                )
            max_mireds = color_temperature_kelvin_to_mired(
                self.config.get(CONF_MIN_COLOR_TEMP_KELVIN)
                or attributes.get(
                    LightEntityCapabilityAttribute.MIN_COLOR_TEMP_KELVIN,
                    DEFAULT_MIN_COLOR_TEMP,
                )
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

        self.adaptive_lighting: AdaptiveLightingController | None = None
        if self._adaptive_lighting_enabled:
            self.adaptive_lighting = AdaptiveLightingController(
                self, serv_light, self.entity_id
            )
        elif self.driver.entry_id:
            # A schedule stored for this entity is orphaned once the option is
            # gone; drop it so it cannot resurrect on a later re-enable.
            self.hass.async_create_task(
                async_delete_stored_schedule(
                    self.hass, self.driver.entry_id, self.entity_id
                )
            )

        self.async_update_state(state)
        serv_light.setter_callback = self._set_chars

    @override
    @callback
    @pyhap_callback  # type: ignore[untyped-decorator]
    def run(self) -> None:
        """Start the accessory and resume a saved adaptive lighting schedule."""
        super().run()
        if self.adaptive_lighting:
            self.adaptive_lighting.schedule_restore()

    @override
    @callback
    def async_stop(self) -> None:
        """Cancel subscriptions, the pending coalesced write and adaptive timers."""
        if self._event_timer:
            self._event_timer()
            self._event_timer = None
        self._pending_events = {}
        super().async_stop()
        if self.adaptive_lighting:
            self.adaptive_lighting.stop()

    @callback
    def async_set_adaptive_color_temperature(self, mireds: int) -> None:
        """Apply a colour temperature computed from the transition curve."""
        # Bulbs on the RGBWW/RGB paths do not report color_temp_kelvin, so the
        # state update would leave the advertised characteristic stale.
        self.char_color_temp.set_value(mireds)
        self.char_color_temp.notify()
        self._set_chars({CHAR_COLOR_TEMPERATURE: mireds})

    def _set_chars(self, char_values: dict[str, Any]) -> None:
        _LOGGER.debug("Light _set_chars: %s", char_values)
        # The adaptive lighting characteristics share the light service, so a
        # schedule written by the Home app arrives here too. The controller has
        # already handled it through its own setter and it says nothing about
        # brightness or colour; left in, it falls through to the SERVICE_TURN_ON
        # default below and switches the light on by itself.
        char_values = {
            char: value
            for char, value in char_values.items()
            if char not in ADAPTIVE_LIGHTING_CHARS
        }
        if not char_values:
            return
        if self.adaptive_lighting and (
            char_values.keys() & {CHAR_COLOR_TEMPERATURE, CHAR_HUE, CHAR_SATURATION}
        ):
            # HomeKit expects adaptive lighting to stop on a manual colour change.
            self.adaptive_lighting.notify_manual_change()
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
        service = LightService.TURN_ON
        params: dict[str, Any] = {ATTR_ENTITY_ID: self.entity_id}
        has_on = CHAR_ON in char_values

        # Adaptive lighting writes colour to accessories that are off, and a
        # write without CHAR_ON would fall through to the SERVICE_TURN_ON
        # default below and switch the light on by itself. A colour only write
        # is never a request to turn a light on, unless we just asked for On
        # and the state has not caught up yet.
        if (
            self.adaptive_lighting
            and not has_on
            and char_values
            and not char_values.keys() - COLOR_ONLY_CHARS
        ):
            state = self.hass.states.get(self.entity_id)
            if (state is None or state.state != STATE_ON) and not self._pending_turn_on:
                _LOGGER.debug(
                    "%s: ignoring colour only write %s, the light is off",
                    self.entity_id,
                    char_values,
                )
                self.adaptive_lighting.discard_applied()
                return

        if has_on:
            self._pending_turn_on = bool(char_values[CHAR_ON])
            if not char_values[CHAR_ON]:
                service = LightService.TURN_OFF
            events.append(f"Set state to {char_values[CHAR_ON]}")

        brightness_pct = None
        if CHAR_BRIGHTNESS in char_values:
            if char_values[CHAR_BRIGHTNESS] == 0:
                if has_on:
                    events[-1] = "Set state to 0"
                else:
                    events.append("Set state to 0")
                service = LightService.TURN_OFF
            else:
                brightness_pct = char_values[CHAR_BRIGHTNESS]
            events.append(f"brightness at {char_values[CHAR_BRIGHTNESS]}%")

        if service == LightService.TURN_OFF:
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
            if (rgb := self._warm_rgb_color(temp)) is not None:
                params[LightServiceArgument.RGB_COLOR] = rgb
            elif self.color_temp_supported:
                params[LightServiceArgument.COLOR_TEMP_KELVIN] = (
                    color_temperature_mired_to_kelvin(temp)
                )
            elif self.rgbww_supported:
                params[LightServiceArgument.RGBWW_COLOR] = color_temperature_to_rgbww(
                    color_temperature_mired_to_kelvin(temp),
                    bright_val,
                    color_temperature_mired_to_kelvin(self.max_mireds),
                    color_temperature_mired_to_kelvin(self.min_mireds),
                )
            elif self.rgbw_supported:
                params[LightServiceArgument.RGBW_COLOR] = (*(0,) * 3, bright_val)
            elif self.white_supported:
                params[LightServiceArgument.WHITE] = bright_val

        elif CHAR_HUE in char_values or CHAR_SATURATION in char_values:
            hue_sat = (
                char_values.get(CHAR_HUE, self.char_hue.value),
                char_values.get(CHAR_SATURATION, self.char_saturation.value),
            )
            _LOGGER.debug("%s: Set hs_color to %s", self.entity_id, hue_sat)
            events.append(f"set color at {hue_sat}")
            params[LightServiceArgument.HS_COLOR] = hue_sat

        if (
            brightness_pct
            and LightServiceArgument.RGBWW_COLOR not in params
            and LightServiceArgument.RGBW_COLOR not in params
        ):
            params[LightServiceArgument.BRIGHTNESS_PCT] = brightness_pct

        _LOGGER.debug(
            "Calling light service with params: %s -> %s", char_values, params
        )
        self.hass.async_create_task(
            self._async_call_light_service(
                service,
                params,
                ", ".join(events),
                CHAR_COLOR_TEMPERATURE in char_values,
            ),
            eager_start=True,
        )

    async def _async_call_light_service(
        self, service: str, params: dict[str, Any], value: str, sets_colour: bool
    ) -> None:
        """Call the light service and let adaptive lighting know if it failed."""
        succeeded = await self.async_call_service_and_wait(
            LIGHT_DOMAIN, service, params, value
        )
        if not succeeded and sets_colour and self.adaptive_lighting:
            self.adaptive_lighting.discard_applied()

    def _warm_rgb_color(self, mireds: int) -> tuple[int, ...] | None:
        """Return the colour for a temperature below the white channel's floor.

        Some bulbs clamp or go dark below a colour temperature they still
        advertise, but can show a warmer tone in colour mode. Below the
        configured floor the temperature is blended towards that colour. The
        blend starts from a colour that matches the white floor on that bulb,
        since a bulb's colour LEDs rarely reproduce its white ones.
        """
        floor = self.config.get(CONF_RGB_BELOW_KELVIN)
        kelvin = color_temperature_mired_to_kelvin(mireds)
        if not floor or not self.color_supported or kelvin >= floor:
            return None
        warmest = color_temperature_mired_to_kelvin(self.max_mireds)
        ratio = min(1, (floor - kelvin) / max(1, floor - warmest))
        white = self.config.get(CONF_FLOOR_RGB_COLOR) or color_temperature_to_rgb(floor)
        return tuple(
            round(start + (end - start) * ratio)
            for start, end in zip(white, self.config[CONF_WARM_RGB_COLOR], strict=True)
        )

    @callback
    @override
    def async_update_state(self, new_state: State) -> None:
        """Update light after state change."""
        # Handle State
        state = new_state.state
        attributes = new_state.attributes
        if state == STATE_ON:
            self._pending_turn_on = False
        color_mode = attributes.get(LightEntityStateAttribute.COLOR_MODE)
        self.char_on.set_value(int(state == STATE_ON))
        color_mode_changed = self._previous_color_mode != color_mode
        self._previous_color_mode = color_mode

        # Handle Brightness
        if (
            self.brightness_supported
            and (brightness := attributes.get(LightEntityStateAttribute.BRIGHTNESS))
            is not None
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
            if color_temp := attributes.get(
                LightEntityStateAttribute.COLOR_TEMP_KELVIN
            ):
                hue, saturation = color_temperature_to_hs(color_temp)
            elif color_mode == ColorMode.WHITE:
                hue, saturation = 0, 0
            elif (
                (hue_sat := attributes.get(LightEntityStateAttribute.HS_COLOR))
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
                color_temp_kelvin = attributes.get(
                    LightEntityStateAttribute.COLOR_TEMP_KELVIN
                )
                if color_temp_kelvin is not None:
                    color_temp = color_temperature_kelvin_to_mired(color_temp_kelvin)
            elif color_mode == ColorMode.WHITE:
                color_temp = self.min_mireds
            if isinstance(color_temp, (int, float)):
                self.char_color_temp.set_value(round(color_temp, 0))
                if color_mode_changed:
                    self.char_color_temp.notify()
