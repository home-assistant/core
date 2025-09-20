"""Constants for the Level Lock integration."""

DOMAIN = "level_lock"

# Config keys
CONF_OAUTH2_BASE_URL = "oauth2_base_url"
CONF_PARTNER_BASE_URL = "partner_base_url"

# Default base URLs (can be overridden via YAML options or other configuration)
DEFAULT_OAUTH2_BASE_URL = "https://oauth2-dev.level.co"
DEFAULT_PARTNER_BASE_URL = "https://sidewalk-dev.level.co"
# DEFAULT_OAUTH2_BASE_URL = "http://localhost:27915"
# DEFAULT_PARTNER_BASE_URL = "http://localhost:15178"

# API paths
OAUTH2_AUTHORIZE_PATH = "/v1/authorize"
OAUTH2_TOKEN_EXCHANGE_PATH = "/v1/token/exchange"
OAUTH2_OTP_CONFIRM_PATH = "/v1/authenticate/otp/confirm"
OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH = "/v1/grant-permissions/accept"
PARTNER_OTP_START_PATH = "/v1/oauth2/otp/start"

# Cloud device API paths (resource server)
# These are used by the lock platform to discover devices and control them.
# If your deployment uses a different resource server base URL than the OAuth2 base,
# adjust the base URL in the platform setup accordingly.
API_LOCKS_LIST_PATH = "/v1/locks"
API_LOCK_STATUS_PATH = "/v1/locks/{lock_id}/status"
API_LOCK_COMMAND_LOCK_PATH = "/v1/locks/{lock_id}/lock"
API_LOCK_COMMAND_UNLOCK_PATH = "/v1/locks/{lock_id}/unlock"
