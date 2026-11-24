"""Constants for the Bbox integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "bbox"
INTEGRATION_TITLE = "Bbox"

DEFAULT_HOST = "mabbox.bytel.fr"
DEFAULT_NAME = "Bbox"

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR]
