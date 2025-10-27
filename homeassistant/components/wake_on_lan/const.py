"""Constants for the Wake-On-LAN component."""

from homeassistant.const import Platform

DOMAIN = "wake_on_lan"
PLATFORMS = [Platform.BUTTON]

CONF_OFF_ACTION = "turn_off"
CONF_ON_GRACE_PERIOD = "on_grace_period"
CONF_OFF_GRACE_PERIOD = "off_grace_period"

DEFAULT_NAME = "Wake on LAN"
DEFAULT_PING_TIMEOUT = 1
