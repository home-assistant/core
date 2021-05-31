"""Constants for the NFAndroidTV integration."""
from homeassistant.const import PERCENTAGE

DOMAIN: str = "nfandroidtv"
CONF_DURATION = "duration"
CONF_FONTSIZE = "fontsize"
CONF_POSITION = "position"
CONF_TRANSPARENCY = "transparency"
CONF_COLOR = "color"
CONF_INTERRUPT = "interrupt"

DEFAULT_DURATION = 5
DEFAULT_FONTSIZE = "medium"
DEFAULT_NAME = "Android TV / Fire TV"
DEFAULT_POSITION = "bottom-right"
DEFAULT_TRANSPARENCY = "default"
DEFAULT_COLOR = "grey"
DEFAULT_INTERRUPT = False
DEFAULT_TIMEOUT = 5
DEFAULT_ICON = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGP6zwAAAgcBApo"
    "cMXEAAAAASUVORK5CYII="
)

ATTR_DURATION = "duration"
ATTR_FONTSIZE = "fontsize"
ATTR_POSITION = "position"
ATTR_TRANSPARENCY = "transparency"
ATTR_COLOR = "color"
ATTR_BKGCOLOR = "bkgcolor"
ATTR_INTERRUPT = "interrupt"
ATTR_IMAGE = "filename2"
ATTR_FILE = "file"
# Attributes contained in file
ATTR_FILE_URL = "url"
ATTR_FILE_PATH = "path"
ATTR_FILE_USERNAME = "username"
ATTR_FILE_PASSWORD = "password"
ATTR_FILE_AUTH = "auth"
# Any other value or absence of 'auth' lead to basic authentication being used
ATTR_FILE_AUTH_DIGEST = "digest"

FONTSIZES = {"small": 1, "medium": 0, "large": 2, "max": 3}

KNOWN_DEVICES = "known_devices"

POSITIONS = {
    "bottom-right": 0,
    "bottom-left": 1,
    "top-right": 2,
    "top-left": 3,
    "center": 4,
}

TRANSPARENCIES = {
    "default": 0,
    f"0{PERCENTAGE}": 1,
    f"25{PERCENTAGE}": 2,
    f"50{PERCENTAGE}": 3,
    f"75{PERCENTAGE}": 4,
    f"100{PERCENTAGE}": 5,
}

COLORS = {
    "grey": "#607d8b",
    "black": "#000000",
    "indigo": "#303F9F",
    "green": "#4CAF50",
    "red": "#F44336",
    "cyan": "#00BCD4",
    "teal": "#009688",
    "amber": "#FFC107",
    "pink": "#E91E63",
}
