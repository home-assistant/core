"""Constants for the Dexcom integration."""

from homeassistant.const import Platform

DOMAIN = "dexcom"
PLATFORMS = [Platform.SENSOR]

CONF_SERVER = "server"

SERVER_OUS = "EU"
SERVER_US = "US"
