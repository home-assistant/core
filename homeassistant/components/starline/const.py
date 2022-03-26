"""StarLine constants."""
import logging

from homeassistant.const import Platform

_LOGGER = logging.getLogger(__package__)

DOMAIN = "starline"
PLATFORMS = [
    Platform.DEVICE_TRACKER,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.LOCK,
    Platform.SWITCH,
]

CONF_APP_ID = "app_id"
CONF_APP_SECRET = "app_secret"
CONF_MFA_CODE = "mfa_code"
CONF_CAPTCHA_CODE = "captcha_code"

DEFAULT_SCAN_INTERVAL = 180  # in seconds
CONF_SCAN_OBD_INTERVAL = "scan_obd_interval"
DEFAULT_SCAN_OBD_INTERVAL = 10800  # 3 hours in seconds

ERROR_AUTH_APP = "error_auth_app"
ERROR_AUTH_USER = "error_auth_user"
ERROR_AUTH_MFA = "error_auth_mfa"

DATA_USER_ID = "user_id"
DATA_SLNET_TOKEN = "slnet_token"
DATA_SLID_TOKEN = "slid_token"
DATA_EXPIRES = "expires"

SERVICE_UPDATE_STATE = "update_state"
SERVICE_SET_SCAN_INTERVAL = "set_scan_interval"
SERVICE_SET_SCAN_OBD_INTERVAL = "set_scan_obd_interval"
