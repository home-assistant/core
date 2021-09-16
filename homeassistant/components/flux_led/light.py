"""Support for FluxLED/MagicHome lights."""

from datetime import timedelta
import logging
import random

from flux_led import WifiLedBulb
import voluptuous as vol

from homeassistant.components.light import (  # COLOR_MODES_BRIGHTNESS,; SUPPORT_BRIGHTNESS,; SUPPORT_COLOR,; SUPPORT_COLOR_TEMP,; SUPPORT_WHITE_VALUE,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    COLOR_MODE_RGB,
    COLOR_MODE_RGBW,
    COLOR_MODE_RGBWW,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    PLATFORM_SCHEMA,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_MODE,
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
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    CONF_AUTOMATIC_ADD,
    CONF_EFFECT_SPEED,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
    SIGNAL_ADD_DEVICE,
    SIGNAL_REMOVE_DEVICE,
)

_LOGGER = logging.getLogger(__name__)

CONF_COLORS = "colors"
CONF_SPEED_PCT = "speed_pct"
CONF_TRANSITION = "transition"
CONF_CUSTOM_EFFECT = "custom_effect"

SUPPORT_FLUX_LED = SUPPORT_EFFECT | SUPPORT_TRANSITION

MODE_DIM = "DIM"
MODE_CCT = "CCT"
MODE_RGB = "RGB"
MODE_RGBW = "RGBW"
MODE_RGBWW = "RGBWW"


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

CUSTOM_EFFECT_SCHEMA = {
    vol.Required(CONF_COLORS): vol.All(
        cv.ensure_list,
        vol.Length(min=1, max=16),
        [vol.All(vol.ExactSequence((cv.byte, cv.byte, cv.byte)), vol.Coerce(tuple))],
    ),
    vol.Optional(CONF_SPEED_PCT, default=50): vol.All(
        vol.Range(min=0, max=100), vol.Coerce(int)
    ),
    vol.Optional(CONF_TRANSITION, default=TRANSITION_GRADUAL): vol.All(
        cv.string, vol.In([TRANSITION_GRADUAL, TRANSITION_JUMP, TRANSITION_STROBE])
    ),
}

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(ATTR_MODE, default=MODE_RGBW): vol.All(
            cv.string, vol.In([MODE_RGBW, MODE_RGBWW, MODE_RGB, MODE_CCT, MODE_DIM])
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


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform and manage importing from YAML."""
    automatic_add = config["automatic_add"]
    devices = {}

    for import_host, import_item in config["devices"].items():
        import_name = import_host
        if import_item:
            import_name = import_item.get("name", import_host)

        devices[import_host.replace(".", "_")] = {
            CONF_NAME: import_name,
            CONF_HOST: import_host,
        }

    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_AUTOMATIC_ADD: automatic_add,
            CONF_DEVICES: devices,
        },
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
    """Represents a Flux Light entity."""

    def __init__(self, unique_id: str, device: dict, effect_speed: int, bulb):
        """Initialize the Flux light entity."""
        self._name = device[CONF_NAME]
        self._unique_id = unique_id
        self._icon = "mdi:lightbulb"
        self._attrs: dict = {}
        self._state = False
        self._brightness = None
        self._color_temp_mired = None
        self._rgbww = None
        self._color_mode = None
        self._current_effect = None
        self._ip_address = device[CONF_HOST]
        self._effect_speed = effect_speed
        self._mode = None
        self._bulb = bulb
        self._color_brightness = None

    async def async_remove_light(self, device: dict):
        """Remove a bulb device when it is removed from options."""

        bulb_id = device["device_id"]

        if self._unique_id != bulb_id:
            return

        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        entity_entry = entity_registry.async_get(self.entity_id)

        device_registry = await self.hass.helpers.device_registry.async_get_registry()
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

    def update_bulb_info(self):
        """Update the bulb information."""
        self._bulb.update_state()

    @Throttle(timedelta(seconds=1))
    def update(self):
        """Fetch the data from this light bulb."""

        try:
            self.update_bulb_info()
        except BrokenPipeError as error:
            _LOGGER.warning("Error updating flux_led: %s", error)
            return

        self._mode = self._bulb.mode
        self._rgbww = [0, 0, 0, 0, 0]
        self._color_temp_mired = None
        hsv_data = [0, 0, 0]

        if self._mode == MODE_CCT:
            color_data = self._bulb.getWhiteTemperature()
            self._brightness = color_data[1]
            self._color_temp_mired = color_util.color_temperature_kelvin_to_mired(
                color_data[0]
            )

        elif self._mode == MODE_RGB:
            self._rgbww = self._bulb.getRgb()
            hsv_data = color_util.color_RGB_to_hsv(*self._rgbww[0:3])
            self._rgbww = color_util.color_hs_to_RGB(*hsv_data[0:2])
            self._color_brightness = round(hsv_data[2] * 2.55)
            self._brightness = self._color_brightness

        elif self._mode == MODE_RGBW:
            self._rgbww = list(self._bulb.getRgbw())
            _, self._brightness = rgbww_brightness(self._rgbww, None)

        elif self._mode == MODE_RGBWW:
            self._rgbww = list(self._bulb.getRgbww())
            _, self._brightness = rgbww_brightness(self._rgbww, None)

        else:
            self._brightness = self._bulb.getWarmWhite255()

        self._current_effect = self._bulb.raw_state[3]

        if self._bulb.is_on and (self._brightness > 0):
            self._state = True
        else:
            self._state = False

    @property
    def unique_id(self):
        """Return the unique ID of the light."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def is_on(self):
        """Return true if the light is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the kelvin value of this light in mired."""
        return self._color_temp_mired

    @property
    def rgb_color(self):
        """Return the rgb color value [int, int, int]."""
        return self._rgbww[0:2]

    @property
    def rgbw_color(self):
        """Return the rgbw color value [int, int, int, int]."""
        return self._rgbww[0:3]

    @property
    def rgbww_color(self):
        """Return the rgbww color value [int, int, int, int, int]."""
        return self._rgbww

    @property
    def supported_color_modes(self):
        """Flag supported color modes."""
        mode_list = set()
        if self._mode == MODE_RGBWW:
            mode_list.add(COLOR_MODE_RGBWW)
        elif self._mode == MODE_RGBW:
            mode_list.add(COLOR_MODE_RGBW)
        elif self._mode == MODE_RGB:
            mode_list.add(COLOR_MODE_RGB)
        elif self._mode == MODE_CCT:
            mode_list.add(COLOR_MODE_COLOR_TEMP)
            mode_list.add(COLOR_MODE_BRIGHTNESS)
        elif self._mode == MODE_DIM:
            mode_list.add(COLOR_MODE_BRIGHTNESS)
        else:
            mode_list.add(COLOR_MODE_ONOFF)
        return mode_list

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        if self._mode == MODE_RGBWW:
            self._color_mode = COLOR_MODE_RGBWW
        elif self._mode == MODE_RGBW:
            self._color_mode = COLOR_MODE_RGBW
        elif self._mode == MODE_RGB:
            self._color_mode = COLOR_MODE_RGB
        elif self._mode == MODE_CCT:
            self._color_mode = COLOR_MODE_COLOR_TEMP
        elif self._mode == MODE_DIM:
            self._color_mode = COLOR_MODE_BRIGHTNESS
        else:
            self._color_mode = COLOR_MODE_BRIGHTNESS

        return self._color_mode

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return FLUX_EFFECT_LIST + [EFFECT_CUSTOM]

    @property
    def effect(self):
        """Return the current effect."""
        current_mode = self._current_effect

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
    def min_mireds(self) -> int:
        """Return the coldest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 154

    @property
    def max_mireds(self) -> int:
        """Return the warmest color_temp that this light supports."""
        # Default to the Philips Hue value that HA has always assumed
        # https://developers.meethue.com/documentation/core-concepts
        return 370

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
        """Turn on the light."""

        rgb = kwargs.get(ATTR_RGB_COLOR)
        rgbw = kwargs.get(ATTR_RGBW_COLOR)
        rgbww = kwargs.get(ATTR_RGBWW_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        color_temp_mired = kwargs.get(ATTR_COLOR_TEMP)
        color_temp_kelvin = None

        if not self._state:
            self._state = True
            self._bulb.turnOn()

        if not effect:

            if brightness:
                self._brightness = brightness

            if self._color_mode == COLOR_MODE_COLOR_TEMP:
                if color_temp_mired:
                    self._color_temp_mired = color_temp_mired

                color_temp_kelvin = color_util.color_temperature_mired_to_kelvin(
                    self._color_temp_mired
                )
                self._bulb.setWhiteTemperature(color_temp_kelvin, self._brightness)

            elif self._color_mode == COLOR_MODE_RGB:
                if rgb:
                    self._rgbww = rgb

                self._bulb.setRgbw(*self._rgbww, brightness=self._brightness)

            elif self._color_mode == COLOR_MODE_RGBW:
                if rgbw:
                    self._rgbww = rgbw
                    _, self._brightness = rgbww_brightness(self._rgbww, None)
                else:
                    self._rgbww, self._brightness = rgbww_brightness(
                        self._rgbww, brightness
                    )

                self._bulb.setRgbw(*self._rgbww[0:4])

            elif self._color_mode == COLOR_MODE_RGBWW:
                if rgbww:
                    self._rgbww = rgbww
                    _, self._brightness = rgbww_brightness(self._rgbww, None)
                else:
                    self._rgbww, self._brightness = rgbww_brightness(
                        self._rgbww, brightness
                    )

                self._bulb.setRgbw(*self._rgbww[0:4], w2=self._rgbww[4])

            else:
                self._bulb.setWarmWhite255(brightness)

            return

        if effect == EFFECT_RANDOM:
            color_red = random.randint(0, 255)
            color_green = random.randint(0, 255)
            color_blue = random.randint(0, 255)

            self._rgbww = (color_red, color_green, color_blue)
            _, _, self._brightness = (
                list(color_util.color_RGB_to_hsv(*self._rgbww)) * 2.55
            )
            self._bulb.setRgbw(*self._rgbww)

            return

        if effect in EFFECT_MAP:
            self._current_effect = effect
            self._bulb.setPresetPattern(EFFECT_MAP[effect], self._effect_speed)

            return

    def turn_off(self, **kwargs):
        """Turn off the light."""

        self._state = False
        self._bulb.turnOff()

    def set_custom_effect(self, colors: list, speed_pct: int, transition: str):
        """Define custom service to set a custom effect on the lights."""

        if not self.is_on:
            self.turn_on()

        self._bulb.setCustomPattern(colors, speed_pct, transition)

        self._state = True


def rgbww_brightness(rgbww_data, brightness_255=None):
    """Return non-normalized RGB adjusted to brightnes."""

    ww_brightness_255 = None
    cw_brightness_255 = None
    color_brightness_255 = None
    current_brightness_255 = None
    change_brightness_pct = None
    new_brightness_255 = None
    hsv_data = [0, 0, 0]
    rgbww = [0, 0, 0, 0, 0]

    ww_brightness_255 = rgbww_data[3]

    hsv_data = list(color_util.color_RGB_to_hsv(*rgbww_data[0:3]))
    color_brightness_255 = round(hsv_data[2] * 2.55)

    if len(rgbww_data) == 5:
        cw_brightness_255 = rgbww_data[4]
        current_brightness_255 = round(
            (ww_brightness_255 + color_brightness_255 + cw_brightness_255) / 3
        )
    else:
        cw_brightness_255 = 0
        current_brightness_255 = round((ww_brightness_255 + color_brightness_255) / 2)

    if brightness_255 and brightness_255 != current_brightness_255:

        if brightness_255 < current_brightness_255:
            change_brightness_pct = (
                current_brightness_255 - brightness_255
            ) / current_brightness_255
            ww_brightness_255 = round(ww_brightness_255 * (1 - change_brightness_pct))
            color_brightness_255 = round(
                color_brightness_255 * (1 - change_brightness_pct)
            )
            cw_brightness_255 = round(cw_brightness_255 * (1 - change_brightness_pct))

        else:
            change_brightness_pct = (brightness_255 - current_brightness_255) / (
                255 - current_brightness_255
            )
            ww_brightness_255 = round(
                (255 - ww_brightness_255) * (change_brightness_pct) + ww_brightness_255
            )
            color_brightness_255 = round(
                (255 - color_brightness_255) * (change_brightness_pct)
                + color_brightness_255
            )
            cw_brightness_255 = round(
                (255 - cw_brightness_255) * (change_brightness_pct) + cw_brightness_255
            )

        hsv_data[2] = (color_brightness_255 / 255) * 100
        rgbww[0:3] = list(
            color_util.color_hsv_to_RGB(hsv_data[0], hsv_data[1], hsv_data[2])
        )
        rgbww[3] = ww_brightness_255
        if len(rgbww_data) == 5:
            rgbww[4] = cw_brightness_255

        new_brightness_255 = brightness_255

    else:
        new_brightness_255 = current_brightness_255
        rgbww = rgbww_data

    return (rgbww, new_brightness_255)
