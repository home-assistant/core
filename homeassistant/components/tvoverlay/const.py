"""Constants for the TVOverlay for Android TV integration."""

DOMAIN: str = "tvoverlay"
DATA_HASS_CONFIG = "tvoverlay_hass_config"

DEFAULT_NAME = "TVOverlay"
DEFAULT_TIMEOUT = 5

ATTR_ID = "id"
ATTR_APP_TITLE = "app_title"
ATTR_SOURCE_NAME = "source_name"
ATTR_APP_ICON = "app_icon"
ATTR_BADGE_ICON = "badge_icon"
ATTR_BADGE_COLOR = "badge_color"
ATTR_POSITION = "position"
ATTR_DURATION = "duration"

# Attributes contained in image
ATTR_IMAGE = "image"
ATTR_IMAGE_URL = "url"
ATTR_IMAGE_PATH = "path"
ATTR_IMAGE_ICON = "mdi_icon"
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
