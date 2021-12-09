"""Constants for the WLED integration."""
from datetime import timedelta
import logging
from typing import Final

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
ATTR_ON = "on"
ATTR_SEGMENT_ID = "segment_id"
ATTR_SOFTWARE_VERSION = "sw_version"
ATTR_SPEED = "speed"
ATTR_TARGET_BRIGHTNESS = "target_brightness"
ATTR_UDP_PORT = "udp_port"

# Device classes
DEVICE_CLASS_WLED_LIVE_OVERRIDE: Final = "wled__live_override"
