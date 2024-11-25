"""Constants for the Weheat integration."""

from logging import Logger, getLogger

DOMAIN = "weheat"
MANUFACTURER = "Weheat"
ENTRY_TITLE = "Weheat cloud"
ERROR_DESCRIPTION = "error_description"

OAUTH2_AUTHORIZE = (
    "https://auth.weheat.nl/auth/realms/Weheat/protocol/openid-connect/auth/"
)
OAUTH2_TOKEN = (
    "https://auth.weheat.nl/auth/realms/Weheat/protocol/openid-connect/token/"
)
API_URL = "https://api.weheat.nl"
OAUTH2_SCOPES = ["openid", "offline_access"]


UPDATE_INTERVAL = 30

LOGGER: Logger = getLogger(__package__)

DISPLAY_PRECISION_WATTS = 0
DISPLAY_PRECISION_COP = 1
DISPLAY_PRECISION_WATER_TEMP = 1
