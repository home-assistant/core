"""Constants for the Kodi platform."""
DOMAIN = "kodi"

CONF_WS_PORT = "ws_port"

DATA_CONNECTION = "connection"
DATA_REMOVE_LISTENER = "remove_listener"

DEFAULT_PORT = 8080
DEFAULT_SSL = False
DEFAULT_TIMEOUT = 5
DEFAULT_WS_PORT = 9090

EVENT_TURN_OFF = "kodi.turn_off"
EVENT_TURN_ON = "kodi.turn_on"

WS_SCREENSAVER = {
    "id": "screensaver",
    "name": "Screensaver",
    "on": "GUI.OnScreensaverActivated",
    "off": "GUI.OnScreensaverDeactivated",
    "boolean": "System.ScreenSaverActive",
}
WS_DPMS = {
    "id": "energy_saving",
    "name": "Energy saving",
    "on": "GUI.OnDPMSActivated",
    "off": "GUI.OnDPMSDeactivated",
    "boolean": "System.DPMSActive",
}
