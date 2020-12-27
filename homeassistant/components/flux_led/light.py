"""Support for Flux lights."""
import logging
import random

from flux_led import BulbScanner, WifiLedBulb
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

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._bulb is not None

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
        if self._custom_effect:
            return FLUX_EFFECT_LIST + [EFFECT_CUSTOM]

        return FLUX_EFFECT_LIST

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

        if effect == EFFECT_CUSTOM:
            if self._custom_effect:
                self._bulb.setCustomPattern(
                    self._custom_effect[CONF_COLORS],
                    self._custom_effect[CONF_SPEED_PCT],
                    self._custom_effect[CONF_TRANSITION],
                )
            return

        # Effect selection
        if effect in EFFECT_MAP:
            self._bulb.setPresetPattern(EFFECT_MAP[effect], self._effect_speed)
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

    def update(self):
        """Synchronize state with bulb."""
        if not self.available:
            try:
                self._connect()
                self._error_reported = False
            except OSError:
                self._disconnect()
                if not self._error_reported:
                    _LOGGER.warning(
                        "Failed to connect to bulb %s, %s", self._ipaddr, self._name
                    )
                    self._error_reported = True
                return

        self._bulb.update_state(retry=2)
