"""Constants for the WLED integration."""

from datetime import timedelta
import logging

from wled import LightCapability

from homeassistant.components.light import ColorMode

# Integration domain
DOMAIN = "wled"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)
RELEASES_SCAN_INTERVAL = timedelta(hours=3)

# Options
CONF_KEEP_MAIN_LIGHT = "keep_master_light"
DEFAULT_KEEP_MAIN_LIGHT = False

# Attributes
ATTR_CCT = "cct"
ATTR_COLOR_PRIMARY = "color_primary"
ATTR_DURATION = "duration"
ATTR_FADE = "fade"
ATTR_INTENSITY = "intensity"
ATTR_ON = "on"
ATTR_SEGMENT_ID = "segment_id"
ATTR_SOFTWARE_VERSION = "sw_version"
ATTR_SPEED = "speed"
ATTR_TARGET_BRIGHTNESS = "target_brightness"
ATTR_UDP_PORT = "udp_port"

# Static values
COLOR_TEMP_K_MIN = 2000
COLOR_TEMP_K_MAX = 6535


LIGHT_CAPABILITIES_COLOR_MODE_MAPPING: dict[LightCapability, list[ColorMode]] = {
    LightCapability.NONE: [
        ColorMode.ONOFF,
    ],
    LightCapability.RGB_COLOR: [
        ColorMode.RGB,
    ],
    LightCapability.WHITE_CHANNEL: [
        ColorMode.BRIGHTNESS,
    ],
    LightCapability.RGB_COLOR | LightCapability.WHITE_CHANNEL: [
        ColorMode.RGBW,
    ],
    LightCapability.COLOR_TEMPERATURE: [
        ColorMode.COLOR_TEMP,
    ],
    LightCapability.RGB_COLOR | LightCapability.COLOR_TEMPERATURE: [
        ColorMode.RGBWW,
    ],
    LightCapability.WHITE_CHANNEL | LightCapability.COLOR_TEMPERATURE: [
        ColorMode.COLOR_TEMP,
    ],
    LightCapability.RGB_COLOR
    | LightCapability.WHITE_CHANNEL
    | LightCapability.COLOR_TEMPERATURE: [
        ColorMode.COLOR_TEMP,
        ColorMode.RGBW,
    ],
    LightCapability.MANUAL_WHITE: [
        ColorMode.BRIGHTNESS,
    ],
    LightCapability.RGB_COLOR | LightCapability.MANUAL_WHITE: [
        ColorMode.RGBW,
    ],
    LightCapability.WHITE_CHANNEL | LightCapability.MANUAL_WHITE: [
        ColorMode.BRIGHTNESS,
    ],
    LightCapability.RGB_COLOR
    | LightCapability.WHITE_CHANNEL
    | LightCapability.MANUAL_WHITE: [
        ColorMode.RGBW,
        ColorMode.WHITE,
    ],
    LightCapability.COLOR_TEMPERATURE | LightCapability.MANUAL_WHITE: [
        ColorMode.COLOR_TEMP,
        ColorMode.WHITE,
    ],
    LightCapability.RGB_COLOR
    | LightCapability.COLOR_TEMPERATURE
    | LightCapability.MANUAL_WHITE: [
        ColorMode.RGBW,
        ColorMode.COLOR_TEMP,
    ],
    LightCapability.WHITE_CHANNEL
    | LightCapability.COLOR_TEMPERATURE
    | LightCapability.MANUAL_WHITE: [
        ColorMode.COLOR_TEMP,
        ColorMode.WHITE,
    ],
    LightCapability.RGB_COLOR
    | LightCapability.WHITE_CHANNEL
    | LightCapability.COLOR_TEMPERATURE
    | LightCapability.MANUAL_WHITE: [
        ColorMode.RGBW,
        ColorMode.COLOR_TEMP,
    ],
}
