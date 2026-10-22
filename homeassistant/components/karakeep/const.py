"""Constants for the Karakeep integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "karakeep"

DEFAULT_VERIFY_SSL = True
UPDATE_INTERVAL = timedelta(seconds=300)

PLATFORMS = [Platform.SENSOR]
