"""Constants for Heiman integration."""

DOMAIN = "heiman_home"

# OAuth 2.0 Configuration
OAUTH_AUTHORIZE_URL = "https://spapi.heiman.cn/api-auth/system/auth/ha/oauth/authorize"
OAUTH_TOKEN_URL = "https://spapi.heiman.cn/api-auth/oauth/token"

# API Endpoint
API_BASE_URL = "https://spapi.heiman.cn"

# Configuration Items
CONF_HOME_ID = "home_id"
CONF_USER_ID = "user_id"
CONF_REFRESH_TOKEN = "refresh_token"

# Platform Definitions
PLATFORMS = ["sensor"]
