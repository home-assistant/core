"""Constants for the Nice G.O. integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "nice_go"

# Configuration
CONF_SITE_ID = "site_id"
CONF_DEVICE_ID = "device_id"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_REFRESH_TOKEN_CREATION_TIME = "refresh_token_creation_time"

REFRESH_TOKEN_EXPIRY_TIME = timedelta(days=30)

SUPPORTED_DEVICE_TYPES = {
    Platform.LIGHT: ["WallStation", "WallStation_ESP32"],
    Platform.SWITCH: ["WallStation", "WallStation_ESP32"],
}
KNOWN_UNSUPPORTED_DEVICE_TYPES = {
    Platform.LIGHT: ["Mms100"],
    Platform.SWITCH: ["Mms100"],
}

UNSUPPORTED_DEVICE_WARNING = (
    "Device '%s' has unknown device type '%s', "
    "which is not supported by this integration. "
    "We try to support it with a cover and event entity, but nothing else. "
    "Please create an issue with your device model in additional info"
    " at https://github.com/home-assistant/core/issues/new"
    "?assignees=&labels=&projects=&template=bug_report.yml"
    "&title=New%%20Nice%%20G.O.%%20device%%20type%%20'%s'%%20found"
)
