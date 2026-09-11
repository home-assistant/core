"""Constants for Axle Energy."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "axle"
PLATFORMS = [Platform.SENSOR]
UPDATE_INTERVAL = timedelta(minutes=10)
