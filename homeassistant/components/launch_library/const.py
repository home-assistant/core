"""Constants for launch_library."""
from homeassistant.const import Platform

DOMAIN = "launch_library"
PLATFORMS = [Platform.SENSOR]
UPDATECOORDINATOR = "coordinator"

ICON_ROCKET = "mdi:orbit"

ATTR_AGENCY = "agency"
ATTR_AGENCY_COUNTRY_CODE = "agency_country_code"
ATTR_LAUNCH_TIME = "launch_time"
ATTR_STREAM = "stream"

ATTRIBUTION = "Data provided by Launch Library."
