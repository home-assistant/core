"""Constants for the ComfoConnect integration."""

from homeassistant.const import Platform

DOMAIN = "comfoconnect"

PLATFORMS: list[Platform] = [Platform.FAN, Platform.SENSOR]

SIGNAL_COMFOCONNECT_UPDATE_RECEIVED = "comfoconnect_update_received_{}"

CONF_USER_AGENT = "user_agent"

DEFAULT_NAME = "ComfoAir Q"
DEFAULT_PIN = 0000
DEFAULT_TOKEN = "00000000000000000000000000000001"
DEFAULT_USER_AGENT = "Home Assistant"
