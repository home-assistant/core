"""Constants for the Axis component."""

import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN = "axis"

ATTR_MANUFACTURER = "Axis Communications AB"

CONF_STREAM_PROFILE = "stream_profile"
CONF_VIDEO_SOURCE = "video_source"

DEFAULT_EVENTS = True
DEFAULT_STREAM_PROFILE = "No stream profile"
DEFAULT_TRIGGER_TIME = 0
DEFAULT_VIDEO_SOURCE = "No video source"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CAMERA, Platform.LIGHT, Platform.SWITCH]
