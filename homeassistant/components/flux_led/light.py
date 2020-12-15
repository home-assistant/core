"""Support for FluxLED/MagicHome lights."""

from datetime import timedelta
import logging
import random
import time

from flux_led import WifiLedBulb

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import ATTR_MODE, CONF_HOST, CONF_NAME, CONF_PROTOCOL
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

from .const import (
    CONF_AUTOMATIC_ADD,
    CONF_DEVICES,
    CONF_EFFECT_SPEED,
    DEFAULT_EFFECT_SPEED,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONF_CUSTOM_EFFECT = "custom_effect"
CONF_COLORS = "colors"
CONF_SPEED_PCT = "speed_pct"
CONF_TRANSITION = "transition"

SUPPORT_FLUX_LED = SUPPORT_BRIGHTNESS | SUPPORT_EFFECT | SUPPORT_COLOR

MODE_RGB = "rgb"
MODE_RGBW = "rgbw"

# This mode enables white value to be controlled by brightness.
# RGB value is ignored when this mode is specified.
MODE_WHITE = "w"

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

FLUX_EFFECT_LIST = sorted(list(EFFECT_MAP)) + [EFFECT_RANDOM]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the platform and manage importing from YAML."""
    automatic_add = config["automatic_add"]
    devices = {}

    for import_host, import_item in config["devices"].items():
        import_name = import_host
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
    config_auto = entry.options["global"].get(
        CONF_AUTOMATIC_ADD, entry.data[CONF_AUTOMATIC_ADD]
    )
    config_devices = entry.data[CONF_DEVICES]
    config_options = entry.options

    lights = []

    if config_auto:
        # Find the bulbs on the LAN
        scanner = BulbScanner()
        await hass.async_add_executor_job(scanner.scan)

        for device in scanner.getBulbInfo():
            device_id = device["ipaddr"].replace(".", "_")
            if device_id not in config_devices:
                config_devices[device_id] = device

    for device_id, device in config_devices.items():
        add_device = {}
        add_device["name"] = device.get("name", device_id)
        add_device[CONF_HOST] = device[CONF_HOST]
        add_device[CONF_PROTOCOL] = None
        add_device[ATTR_MODE] = None
        add_device[CONF_CUSTOM_EFFECT] = None
        add_device[CONF_EFFECT_SPEED] = config_options.get(device_id, {}).get(
            CONF_EFFECT_SPEED,
            config_options.get("global", {}).get(
                CONF_EFFECT_SPEED, DEFAULT_EFFECT_SPEED
            ),
        )

        light = FluxLight(add_device)
        lights.append(light)

    async_add_entities(lights)


class FluxLight(LightEntity):
    """Representation of a Flux light."""

    def __init__(self, device):
        """Initialize the light."""
        self._name = device["name"]
        self._ipaddr = device[CONF_HOST]
        self._protocol = device[CONF_PROTOCOL]
        self._mode = device[ATTR_MODE]
        self._custom_effect = device[CONF_CUSTOM_EFFECT]
        self._effect_speed = device[CONF_EFFECT_SPEED]
        self._bulb = None
        self._error_reported = False

    def _connect(self):
        """Connect to Flux light."""

        self._bulb = WifiLedBulb(self._ipaddr, timeout=5)
        if self._protocol:
            self._bulb.setProtocol(self._protocol)

        # After bulb object is created the status is updated. We can
        # now set the correct mode if it was not explicitly defined.
        if not self._mode:
            if self._bulb.rgbwcapable:
                self._mode = MODE_RGBW
            else:
                self._mode = MODE_RGB

    def _disconnect(self):
        """Disconnect from Flux light."""
        self._bulb = None

    def unique_id(self):
        """Return the unique ID of the light."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the light."""
        return self._name

    @property
    def available(self):
        """Return the device information."""
        device_name = "FluxLED/Magic Home"
        device_model = self._model

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._unique_id)},
            ATTR_NAME: self._name,
            ATTR_MANUFACTURER: device_name,
            ATTR_MODEL: device_model,
        }

    async def async_turn_on(self, **kwargs):
        """Turn on the light."""

        rgb = None
        hs_color = kwargs.get(ATTR_HS_COLOR)

        if hs_color:
            rgb = color_util.color_hs_to_RGB(*hs_color)

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        effect = kwargs.get(ATTR_EFFECT)
        white = kwargs.get(ATTR_WHITE_VALUE)

        if effect == EFFECT_RANDOM:
            color_red = random.randint(0, 255)
            color_green = random.randint(0, 255)
            color_blue = random.randint(0, 255)

            self._bulb.setRgbw(
                r=color_red,
                g=color_green,
                b=color_blue,
            )

            self._hs_color = color_util.color_RGB_to_hs(
                color_red,
                color_green,
                color_blue,
            )
            self._last_update = time.time()

            return

        if effect in EFFECT_MAP:
<<<<<<< HEAD
            self._bulb.setPresetPattern(EFFECT_MAP[effect], self._effect_speed)
            return
=======
            self._bulb.setPresetPattern(EFFECT_MAP[effect], DEFAULT_SPEED)

        if not brightness:
            brightness = self._last_brightness

        self._last_brightness = brightness
        self._brightness = brightness
>>>>>>> Initial commit of updated flux_led component.

        if not rgb:
            rgb = color_util.color_hs_to_RGB(*self._last_hs_color)

        self._hs_color = color_util.color_RGB_to_hs(*tuple(rgb))

        if not white and self._mode == MODE_RGBW:
            white = self.white_value

        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=brightness)

        elif self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=white, brightness=brightness)

        else:
            self._bulb.setRgb(*tuple(rgb), brightness=brightness)

        self._state = True
        self._last_update = time.time()

    async def async_turn_off(self, **kwargs):
        """Turn off the light."""

        rgb = self._bulb.getRgb()
        self._last_brightness = self.brightness
        self._last_hs_color = self.hs_color

        if self._mode == MODE_WHITE:
            self._bulb.setRgbw(0, 0, 0, w=0)

        elif self._mode == MODE_RGBW:
            self._bulb.setRgbw(*tuple(rgb), w=0, brightness=0)

        else:
            self._bulb.setRgb(*tuple(rgb), brightness=0)

        self._state = False
        self._last_update = time.time()
