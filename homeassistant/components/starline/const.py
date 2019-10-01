"""StarLine constants."""
import logging

LOGGER = logging.getLogger(__package__)

DOMAIN = "starline"
UPDATE_INTERVAL = 5  # in minutes
PLATFORMS = ["device_tracker", "binary_sensor"]

CONF_APP_ID = "app_id"
CONF_APP_SECRET = "app_secret"
CONF_MFA_CODE = "mfa_code"
CONF_CAPTCHA_CODE = "captcha_code"