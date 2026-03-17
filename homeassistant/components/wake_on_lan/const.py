"""Constants for the Wake-On-LAN component."""

from homeassistant.const import Platform

DOMAIN = "wake_on_lan"
PLATFORMS = [Platform.BUTTON]

CONF_OFF_ACTION = "turn_off"
CONF_BROADCAST_INTERFACE: Final = "broadcast_interface"

DEFAULT_NAME = "Wake on LAN"
DEFAULT_PING_TIMEOUT = 1
