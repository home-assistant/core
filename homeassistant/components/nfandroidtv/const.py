"""Constants for the NFAndroidTV integration."""

DOMAIN: str = "nfandroidtv"
CONF_DURATION = "duration"
CONF_FONTSIZE = "fontsize"
CONF_POSITION = "position"
CONF_TRANSPARENCY = "transparency"
CONF_COLOR = "color"
CONF_INTERRUPT = "interrupt"

DATA_HASS_CONFIG = "nfandroid_hass_config"

DEFAULT_NAME = "Android TV / Fire TV"
DEFAULT_TIMEOUT = 5

ATTR_DURATION = "duration"
ATTR_FONTSIZE = "fontsize"
ATTR_POSITION = "position"
ATTR_TRANSPARENCY = "transparency"
ATTR_COLOR = "color"
ATTR_BKGCOLOR = "bkgcolor"
ATTR_INTERRUPT = "interrupt"
ATTR_IMAGE = "image"
# Attributes contained in image
ATTR_IMAGE_URL = "url"
ATTR_IMAGE_PATH = "path"
ATTR_IMAGE_USERNAME = "username"
ATTR_IMAGE_PASSWORD = "password"
ATTR_IMAGE_AUTH = "auth"
ATTR_ICON = "icon"
# Attributes contained in icon
ATTR_ICON_URL = "url"
ATTR_ICON_PATH = "path"
ATTR_ICON_USERNAME = "username"
ATTR_ICON_PASSWORD = "password"
ATTR_ICON_AUTH = "auth"
# Any other value or absence of 'auth' lead to basic authentication being used
ATTR_IMAGE_AUTH_DIGEST = "digest"
ATTR_ICON_AUTH_DIGEST = "digest"
