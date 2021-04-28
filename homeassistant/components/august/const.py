"""Constants for August devices."""

from datetime import timedelta

DEFAULT_TIMEOUT = 10

CONF_ACCESS_TOKEN_CACHE_FILE = "access_token_cache_file"
CONF_LOGIN_METHOD = "login_method"
CONF_INSTALL_ID = "install_id"

VERIFICATION_CODE_KEY = "verification_code"

NOTIFICATION_ID = "august_notification"
NOTIFICATION_TITLE = "August"

MANUFACTURER = "August Home Inc."

DEFAULT_AUGUST_CONFIG_FILE = ".august.conf"

DATA_AUGUST = "data_august"

DEFAULT_NAME = "August"
DOMAIN = "august"

OPERATION_METHOD_AUTORELOCK = "autorelock"
OPERATION_METHOD_REMOTE = "remote"
OPERATION_METHOD_KEYPAD = "keypad"
OPERATION_METHOD_MOBILE_DEVICE = "mobile"

ATTR_OPERATION_AUTORELOCK = "autorelock"
ATTR_OPERATION_METHOD = "method"
ATTR_OPERATION_REMOTE = "remote"
ATTR_OPERATION_KEYPAD = "keypad"

# Limit battery, online, and hardware updates to hourly
# in order to reduce the number of api requests and
# avoid hitting rate limits
MIN_TIME_BETWEEN_DETAIL_UPDATES = timedelta(hours=1)

# Activity needs to be checked more frequently as the
# doorbell motion and rings are included here
ACTIVITY_UPDATE_INTERVAL = timedelta(seconds=10)

LOGIN_METHODS = ["phone", "email"]

PLATFORMS = ["camera", "binary_sensor", "lock", "sensor"]
