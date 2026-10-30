"""Constants for the AquaLogic integration."""

from homeassistant.const import Platform

DOMAIN = "aqualogic"
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]

UPDATE_TOPIC = f"{DOMAIN}_update"
