"""Constants."""
# Internal constants
DOMAIN = "imou_life"

# Configuration definitions
CONF_API_URL_SG = "openapi-sg.easy4ip.com"
CONF_API_URL_OR = "openapi-or.easy4ip.com"
CONF_API_URL_FK = "openapi-fk.easy4ip.com"

# parameters:
PARAM_API_URL = "api_url"
PARAM_APP_ID = "app_id"
PARAM_APP_SECRET = "app_secret"
PARAM_MOTION_DETECT = "motion_detect"
PARAM_STATUS = "status"
PARAM_STORAGE_USED = "storage_used"
PARAM_CURRENT_OPTION = "current_option"
PARAM_OPTIONS = "options"
PARAM_RESTART_DEVICE = "restart_device"

PLATFORMS = [
    "select",
    "sensor",
    "switch",
    "camera",
    "button"
]
