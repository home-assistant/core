"""Constants for launch_library."""
from homeassistant.const import Platform

DOMAIN = "launch_library"
PLATFORMS = [Platform.SENSOR]
UPDATECOORDINATOR = "coordinator"

ICON_CLOCK = "mdi:clock-outline"
ICON_LUCK = "mdi:horseshoe"
ICON_ROCKET = "mdi:orbit"

ATTR_DESCRIPTION = "description"
ATTR_LAUNCH_FACILITY = "launch_facility"
ATTR_LAUNCH_PAD = "launch_pad"
ATTR_LAUNCH_PROVIDER = "launch_provider"
ATTR_LAUNCH_PAD_COUNTRY_CODE = "launch_facility_country_code"
ATTR_ORBIT = "target_orbit"
ATTR_REASON = "reason"
ATTR_STREAM_LIVE = "stream_live"
ATTR_TYPE = "mission_type"
ATTR_WINDOW_START = "window_start"
ATTR_WINDOW_END = "window_end"

ATTRIBUTION = "Data provided by Launch Library."
