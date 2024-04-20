"""Constants for the Dexcom integration."""

from homeassistant.const import Platform

DOMAIN = "dexcom"
PLATFORMS = [Platform.SENSOR]

MMOL_L = "mmol/L"
MG_DL = "mg/dL"

CONF_SERVER = "server"

SERVER_OUS = "EU"
SERVER_US = "US"
