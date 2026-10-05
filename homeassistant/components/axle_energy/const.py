"""Constants for Axle Energy."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "axle_energy"
PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
UPDATE_INTERVAL = timedelta(minutes=10)
