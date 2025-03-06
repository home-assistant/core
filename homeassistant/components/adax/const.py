"""Constants for the Adax integration."""

from typing import Final

from homeassistant.const import Platform

ACCOUNT_ID: Final = "account_id"
CLOUD = "Cloud"
CONNECTION_TYPE = "connection_type"
DOMAIN: Final = "adax"
LOCAL = "Local"
WIFI_SSID = "wifi_ssid"
WIFI_PSWD = "wifi_pswd"

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]
