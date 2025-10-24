"""Constants for the Kiosker integration."""

DOMAIN = "kiosker"

# Configuration keys
CONF_API_TOKEN = "api_token"
CONF_SSL = "ssl"
CONF_SSL_VERIFY = "ssl_verify"
# Default values
DEFAULT_PORT = 8081
POLL_INTERVAL = 30  # Fixed polling interval in seconds
DEFAULT_SSL = False
DEFAULT_SSL_VERIFY = False

# Service names
SERVICE_NAVIGATE_URL = "navigate_url"
SERVICE_NAVIGATE_REFRESH = "navigate_refresh"
SERVICE_NAVIGATE_HOME = "navigate_home"
SERVICE_NAVIGATE_BACKWARD = "navigate_backward"
SERVICE_NAVIGATE_FORWARD = "navigate_forward"
SERVICE_PRINT = "print"
SERVICE_CLEAR_COOKIES = "clear_cookies"
SERVICE_CLEAR_CACHE = "clear_cache"
SERVICE_SCREENSAVER_INTERACT = "screensaver_interact"
SERVICE_BLACKOUT_SET = "blackout_set"
SERVICE_BLACKOUT_CLEAR = "blackout_clear"

# Attributes
ATTR_URL = "url"
ATTR_VISIBLE = "visible"
ATTR_TEXT = "text"
ATTR_BACKGROUND = "background"
ATTR_FOREGROUND = "foreground"
ATTR_ICON = "icon"
ATTR_EXPIRE = "expire"
ATTR_DISMISSIBLE = "dismissible"
ATTR_BUTTON_BACKGROUND = "button_background"
ATTR_BUTTON_FOREGROUND = "button_foreground"
ATTR_BUTTON_TEXT = "button_text"
ATTR_SOUND = "sound"
