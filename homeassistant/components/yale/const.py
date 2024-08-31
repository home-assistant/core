"""Constants for Yale devices."""

from homeassistant.const import Platform

DEFAULT_TIMEOUT = 25

CONF_ACCESS_TOKEN_CACHE_FILE = "access_token_cache_file"
CONF_BRAND = "brand"
CONF_LOGIN_METHOD = "login_method"
CONF_INSTALL_ID = "install_id"

VERIFICATION_CODE_KEY = "verification_code"

MANUFACTURER = "Yale Home Inc."

DEFAULT_NAME = "Yale"
DOMAIN = "yale"

OPERATION_METHOD_AUTORELOCK = "autorelock"
OPERATION_METHOD_REMOTE = "remote"
OPERATION_METHOD_KEYPAD = "keypad"
OPERATION_METHOD_MANUAL = "manual"
OPERATION_METHOD_TAG = "tag"
OPERATION_METHOD_MOBILE_DEVICE = "mobile"

ATTR_OPERATION_AUTORELOCK = "autorelock"
ATTR_OPERATION_METHOD = "method"
ATTR_OPERATION_REMOTE = "remote"
ATTR_OPERATION_KEYPAD = "keypad"
ATTR_OPERATION_MANUAL = "manual"
ATTR_OPERATION_TAG = "tag"

LOGIN_METHODS = ["phone", "email"]
DEFAULT_LOGIN_METHOD = "email"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.EVENT,
    Platform.LOCK,
    Platform.SENSOR,
]
