"""Constants for the Arris TG2492LG integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "arris_tg2492lg"

PLATFORMS = [Platform.DEVICE_TRACKER]

SCAN_INTERVAL = timedelta(seconds=30)

DEFAULT_HOST = "192.168.178.1"
