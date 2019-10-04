"""StarLine constants."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "starline"
PLATFORMS = ["device_tracker", "binary_sensor", "sensor", "lock", "switch"]

CONF_APP_ID = "app_id"
CONF_APP_SECRET = "app_secret"
CONF_MFA_CODE = "mfa_code"
CONF_CAPTCHA_CODE = "captcha_code"

CONF_UPDATE_INTERVAL = "update_interval"
DEFAULT_UPDATE_INTERVAL = 180  # in seconds

SERVICE_UPDATE_STATE = "update_state"

BATTERY_LEVEL_MIN = 11.8
BATTERY_LEVEL_MAX = 13.0

GSM_LEVEL_MIN = 1
GSM_LEVEL_MAX = 30

ENCODING = "utf-8"
GET = 'GET'
POST = 'POST'
CONNECT_TIMEOUT = 5  # in seconds
READ_TIMEOUT = 120  # in seconds
