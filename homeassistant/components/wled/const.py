"""Constants for the WLED integration."""
from datetime import timedelta
import logging

# Integration domain
DOMAIN = "wled"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)

# Options
CONF_KEEP_MASTER_LIGHT = "keep_master_light"
DEFAULT_KEEP_MASTER_LIGHT = False

# Attributes
ATTR_COLOR_PRIMARY = "color_primary"
ATTR_DURATION = "duration"
ATTR_FADE = "fade"
ATTR_INTENSITY = "intensity"
ATTR_LED_COUNT = "led_count"
ATTR_MAX_POWER = "max_power"
ATTR_ON = "on"
ATTR_PALETTE = "palette"
ATTR_PLAYLIST = "playlist"
ATTR_PRESET = "preset"
ATTR_REVERSE = "reverse"
ATTR_SEGMENT_ID = "segment_id"
ATTR_SOFTWARE_VERSION = "sw_version"
ATTR_SPEED = "speed"
ATTR_TARGET_BRIGHTNESS = "target_brightness"
ATTR_UDP_PORT = "udp_port"

# Services
SERVICE_EFFECT = "effect"
SERVICE_PRESET = "preset"
