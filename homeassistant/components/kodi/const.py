"""Constants for the Kodi integration."""

DOMAIN = "kodi"

CONF_WS_PORT = "ws_port"

DEFAULT_PORT = 8080
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 5
DEFAULT_WS_PORT = 9090

EVENT_TURN_OFF = "kodi.turn_off"
EVENT_TURN_ON = "kodi.turn_on"


def async_signal_screensaver_update(entry_id: str) -> str:
    """Generate a dispatcher signal for Kodi screensaver updates."""
    return f"{DOMAIN}_{entry_id}_screensaver_update"
