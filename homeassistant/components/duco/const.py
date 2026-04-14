"""Constants for the Duco integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "duco"
PLATFORMS = [Platform.FAN, Platform.SENSOR]
SCAN_INTERVAL = timedelta(seconds=30)
