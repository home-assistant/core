"""Support for FluxLED/MagicHome lights."""

from datetime import timedelta
import logging
import random

from flux_led import WifiLedBulb
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.const import (
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODE,
    ATTR_MODEL,
    ATTR_NAME,
    CONF_DEVICES,
    CONF_HOST,
    CONF_NAME,
    CONF_PROTOCOL,
)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.util import Throttle
import homeassistant.util.color as color_util

from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_EFFECT_SPEED,
    DEFAULT_EFFECT_SPEED,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SIGNAL_ADD_DEVICE,
    SIGNAL_REMOVE_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

CONF_COLORS = "colors"
CONF_SPEED_PCT = "speed_pct"
CONF_TRANSITION = "transition"
CONF_CUSTOM_EFFECT = "custom_effect"

SUPPORT_FLUX_LED = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_COLOR
MODE_RGB = "rgb"
MODE_RGBW = "rgbw"
MODE_RGBCW = "rgbcw"
MODE_RGBWW = "rgbww"

# This mode enables white value to be controlled by brightness.
# RGB value is ignored when this mode is specified.
MODE_WHITE = "w"

# Constant color temp values for 2 flux_led special modes
# Warm-white and Cool-white modes
COLOR_TEMP_WARM_VS_COLD_WHITE_CUT_OFF = 285

# List of supported effects which aren't already declared in LIGHT
EFFECT_RED_FADE = "red_fade"
EFFECT_GREEN_FADE = "green_fade"
EFFECT_BLUE_FADE = "blue_fade"
EFFECT_YELLOW_FADE = "yellow_fade"
EFFECT_CYAN_FADE = "cyan_fade"
EFFECT_PURPLE_FADE = "purple_fade"
EFFECT_WHITE_FADE = "white_fade"
EFFECT_RED_GREEN_CROSS_FADE = "rg_cross_fade"
EFFECT_RED_BLUE_CROSS_FADE = "rb_cross_fade"
EFFECT_GREEN_BLUE_CROSS_FADE = "gb_cross_fade"
EFFECT_COLORSTROBE = "colorstrobe"
EFFECT_RED_STROBE = "red_strobe"
EFFECT_GREEN_STROBE = "green_strobe"
EFFECT_BLUE_STROBE = "blue_strobe"
EFFECT_YELLOW_STROBE = "yellow_strobe"
EFFECT_CYAN_STROBE = "cyan_strobe"
EFFECT_PURPLE_STROBE = "purple_strobe"
EFFECT_WHITE_STROBE = "white_strobe"
EFFECT_COLORJUMP = "colorjump"
EFFECT_CUSTOM = "custom"

EFFECT_MAP = {
    EFFECT_COLORLOOP: 0x25,
    EFFECT_RED_FADE: 0x26,
    EFFECT_GREEN_FADE: 0x27,
    EFFECT_BLUE_FADE: 0x28,
    EFFECT_YELLOW_FADE: 0x29,
    EFFECT_CYAN_FADE: 0x2A,
    EFFECT_PURPLE_FADE: 0x2B,
    EFFECT_WHITE_FADE: 0x2C,
    EFFECT_RED_GREEN_CROSS_FADE: 0x2D,
    EFFECT_RED_BLUE_CROSS_FADE: 0x2E,
    EFFECT_GREEN_BLUE_CROSS_FADE: 0x2F,
    EFFECT_COLORSTROBE: 0x30,
    EFFECT_RED_STROBE: 0x31,
    EFFECT_GREEN_STROBE: 0x32,
    EFFECT_BLUE_STROBE: 0x33,
    EFFECT_YELLOW_STROBE: 0x34,
    EFFECT_CYAN_STROBE: 0x35,
    EFFECT_PURPLE_STROBE: 0x36,
    EFFECT_WHITE_STROBE: 0x37,
    EFFECT_COLORJUMP: 0x38,
}
EFFECT_CUSTOM_CODE = 0x60

TRANSITION_GRADUAL = "gradual"
TRANSITION_JUMP = "jump"
TRANSITION_STROBE = "strobe"

FLUX_EFFECT_LIST = sorted(EFFECT_MAP) + [EFFECT_RANDOM]

SERVICE_CUSTOM_EFFECT = "set_custom_effect"

CUSTOM_EFFECT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COLORS): vol.All(
            cv.ensure_list,
            vol.Length(min=1, max=16),
            [
                vol.All(
                    vol.ExactSequence((cv.byte, cv.byte, cv.byte)), vol.Coerce(tuple)
                )
            ],
        ),
        vol.Optional(CONF_SPEED_PCT, default=50): vol.All(
            vol.Range(min=0, max=100), vol.Coerce(int)
        ),
        vol.Optional(CONF_TRANSITION, default=TRANSITION_GRADUAL): vol.All(
            cv.string, vol.In([TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE])
        ),
    }
)

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(ATTR_MODE, default=MODE_RGBW): vol.All(
            cv.string, vol.In([MODE_RGBW, MODE_RGB, MODE_WHITE])
        ),
        vol.Optional(CONF_PROTOCOL): vol.All(cv.string, vol.In(["ledenet"])),
        vol.Optional(CONF_CUSTOM_EFFECT): CUSTOM_EFFECT_SCHEMA,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
        vol.Optional(CONF_AUTOMATIC_ADD, default=False): cv.boolean,
    }
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Flux lights."""

    async def async_new_lights(bulbs: dict):
        """Add new bulbs when they are found or configured."""

        lights = []

        for bulb_id, bulb_details in bulbs.items():
            effect_speed = entry.options.get(bulb_id, {}).get(
                CONF_EFFECT_SPEED,
                entry.options.get("global", {}).get(
                    CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED
                ),
            )

            host = bulb_details[CONF_HOST]
            try:
                bulb = await hass.async_add_executor_job(WifiLedBulb, host)
            except BrokenPipeError as error:
                raise PlatformNotReady(error) from error

            lights.append(
                FluxLight(
                    unique_id=bulb_id,
                    device=bulb_details,
                    effect_speed=effect_speed,
                    bulb=bulb,
                )
            )

        async_add_entities(lights, True)

    await async_new_lights(entry.data[CONF_DEVICES])

    async_dispatcher_connect(hass, SIGNAL_ADD_DEVICE, async_new_lights)

    # register custom_effect service
    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_CUSTOM_EFFECT,
        CUSTOM_EFFECT_SCHEMA,
        "set_custom_effect",
    )


class FluxLight(LightEntity):
    """Representation of a Flux light."""

    def __init__(self, unique_id: str, device: dict, effect_speed: int, bulb):
        """Initialize the light."""
        self._name = device[CONF_NAME]
        self._unique_id = unique_id
        self._icon = "mdi:lightbulb"
        self._attrs: dict = {}
        self._state = False
        self._brightness = None
        self._hs_color = None
        self._white_value = None
        self._current_effect = None
        self._last_brightness = None
        self._last_hs_color = None
        self._ip_address = device[CONF_HOST]
        self._effect_speed = effect_speed
        self._mode = None
        self._get_rgbw = None
        self._get_rgb = None
        self._bulb = bulb

    async def async_remove_light(self, device: dict):
        """Remove a bulb device when it is removed from options."""

        bulb_id = device["device_id"]

        if self._unique_id != bulb_id:
            return

        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        entity_entry = entity_registry.async_get(self.entity_id)

        device_registry = await self.hass.helpers.device_registry.async_get_registry()

        if entity_entry:
            device_entry = device_registry.async_get(entity_entry.device_id)

            if (
                len(
                    async_entries_for_device(
                        entity_registry,
                        entity_entry.device_id,
                        include_disabled_entities=True,
                    )
                )
                == 1
            ):
                # If only this entity exists on this device, remove the device.
                device_registry.async_remove_device(device_entry.id)

            entity_registry.async_remove(self.entity_id)

    async def async_added_to_hass(self):
        """Run when the entity is about to be added to hass."""
        await super().async_added_to_hass()

        async_dispatcher_connect(
            self.hass, SIGNAL_REMOVE_DEVICE, self.async_remove_light
        )

    @property
    def unique_id(self):
        """Return the unique ID of the light."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._bulb.isOn()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self._mode == MODE_WHITE:
            return self.white_value

        return self._bulb.brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return color_util.color_RGB_to_hs(*self._bulb.getRgb())

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._mode == MODE_RGBW:
            return SUPPORT_FLUX_LED | SUPPORT_WHITE_VALUE | SUPPORT_COLOR_TEMP

        if self._mode == MODE_WHITE:
            return SUPPORT_BRIGHTNESS

        return SUPPORT_FLUX_LED

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._bulb.getRgbw()[3]

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return FLUX_EFFECT_LIST + [EFFECT_CUSTOM]

    @property
    def effect(self):
        """Return the current effect."""
        current_mode = self._bulb.raw_state[3]

        if current_mode == EFFECT_CUSTOM_CODE:
            return EFFECT_CUSTOM

        for effect, code in EFFECT_MAP.items():
            if current_mode == code:
                return effect

        return None

    @property
    def device_state_attributes(self):
        """Return the attributes."""
        self._attrs["ip_address"] = self._ip_address

        return self._attrs

    @property
    def device_info(self):
        """Return the device information."""
        device_name = "FluxLED/Magic Home"
        device_model = "LED Lights"

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._unique_id)},
            ATTR_NAME: self._name,
            ATTR_MANUFACTURER: device_name,
            ATTR_MODEL: device_model,
        }

    def turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        if not self.is_on:
            self._bulb.turnOn()

        hs_color = kwargs.get(ATTR_HS_COLOR)

        if hs_color:
            rgb = color_util.color_hs_to_RGB(*hs_color)
        else:
            rgb = None

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        white = kwargs.get(ATTR_WHITE_VALUE)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)

        # handle special modes
        if color_temp is not None:
            if brightness is None:
                brightness = self.brightness
            if color_temp > COLOR_TEMP_WARM_VS_COLD_WHITE_CUT_OFF:
                self._bulb.setRgbw(w=brightness)
            else:
                self._bulb.setRgbw(w2=brightness)
            return

        # Show warning if effect set with rgb, brightness, or white level
        if effect and (brightness or white or rgb):
            _LOGGER.warning(
                "RGB, brightness and white level are ignored when"
                " an effect is specified for a flux bulb"
            )

        # Random color effect
        if effect == EFFECT_RANDOM:
            self._bulb.setRgb(
                random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
            )
            return

        # Effect selection
        if effect in EFFECT_MAP:
            self._bulb.setPresetPattern(EFFECT_MAP[effect], 50)
            return

        # Preserve current brightness on color/white level change
        if brightness is None:
            brightness = self.brightness

        # Preserve color on brightness/white level change
        if rgb is None:
            rgb = self._bulb.getRgb()

        if white is None and self._mode == MODE_RGBW:
            white = self.white_value

        # handle W only mode (use brightness instead of white value)
        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=brightness)

        # handle RGBW mode
        elif self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=white, brightness=brightness)

        # handle RGB mode
        else:
            self._bulb.setRgb(*tuple(rgb), brightness=brightness)

    def turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        self._bulb.turnOff()

    def update_bulb_info(self):
        """Update the bulb information."""
        self._bulb.update_state()
        self._get_rgbw = self._bulb.getRgbw()
        self._get_rgb = self._bulb.getRgb()

    @Throttle(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    def update(self):
        """Fetch the data from this light bulb."""

        try:
            self.update_bulb_info()
        except BrokenPipeError as error:
            _LOGGER.warning("Error updating flux_led: %s", error)
            return

        if self._bulb.protocol:
            if self._bulb.raw_state[9] == self._bulb.raw_state[11]:
                self._mode = MODE_RGBWW
            else:
                self._mode = MODE_RGBCW
        elif self._bulb.mode == "ww":
            self._mode = MODE_WHITE
        elif self._bulb.rgbwcapable and not self._bulb.rgbwprotocol:
            self._mode = MODE_RGBW
        else:
            self._mode = MODE_RGB

        self._hs_color = color_util.color_RGB_to_hs(*self._get_rgb)

        self._current_effect = self._bulb.raw_state[3]

        if self._bulb.is_on:
            self._state = True
        else:
            self._state = False

        if self._state:
            self._last_hs_color = self._hs_color
