"""Constants for the AlphaEss integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "alphaess"
PLATFORMS = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=5)
