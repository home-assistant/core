"""Constants for the Android TV Remote integration."""

from typing import Final

DOMAIN: Final = "androidtv_remote"

CONF_APPS = "apps"
CONF_ENABLE_IME: Final = "enable_ime"
CONF_ENABLE_IME_DEFAULT_VALUE: Final = True
CONF_APP_NAME = "app_name"
CONF_APP_ICON = "app_icon"

# Maps the navigation directions of the remote and media_player platforms
# to Android key codes.
NAVIGATION_KEY_CODES: Final[dict[str, str]] = {
    "up": "DPAD_UP",
    "down": "DPAD_DOWN",
    "left": "DPAD_LEFT",
    "right": "DPAD_RIGHT",
    "select": "DPAD_CENTER",
    "back": "BACK",
    "home": "HOME",
    "menu": "MENU",
}
