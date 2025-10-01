"""Constants for the OpenRGB integration."""

from datetime import timedelta

DOMAIN = "openrgb"

# Defaults
DEFAULT_PORT = 6742
DEFAULT_CLIENT_NAME = "Home Assistant"

# Update interval
SCAN_INTERVAL = timedelta(seconds=15)

DEFAULT_COLOR = (255, 255, 255)
DEFAULT_BRIGHTNESS = 255
OFF_COLOR = (0, 0, 0)

OPENRGB_MODE_OFF = "Off"
OPENRGB_MODE_STATIC = "Static"
OPENRGB_MODE_DIRECT = "Direct"

EFFECT_OFF_OPENRGB_MODES = {OPENRGB_MODE_STATIC, OPENRGB_MODE_DIRECT}
