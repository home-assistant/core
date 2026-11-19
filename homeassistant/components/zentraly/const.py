"""Constants for the Zentraly integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "zentraly"
SCAN_INTERVAL = timedelta(minutes=5)

PLATFORMS = [Platform.CLIMATE]
