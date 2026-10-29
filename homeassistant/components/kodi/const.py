"""Constants for the Kodi integration."""

DOMAIN = "kodi"

CONF_WS_PORT = "ws_port"
# Set once the notify entity of the entry is linked to a YAML notify configuration
CONF_NOTIFY_LINKED = "notify_linked"

DEFAULT_PORT = 8080
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 5
DEFAULT_WS_PORT = 9090
DEFAULT_NOTIFY_ICON = "info"
DEFAULT_NOTIFY_DISPLAYTIME = 10000

EVENT_TURN_OFF = "kodi.turn_off"
EVENT_TURN_ON = "kodi.turn_on"
