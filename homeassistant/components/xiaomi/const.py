"""Constants for the Xiaomi integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "xiaomi"

PLATFORMS = [Platform.DEVICE_TRACKER]

SCAN_INTERVAL = timedelta(seconds=30)

DEFAULT_USERNAME = "admin"
