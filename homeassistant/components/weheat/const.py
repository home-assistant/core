"""Constants for the Weheat integration."""

from logging import Logger, getLogger

DOMAIN = "weheat"

HEAT_PUMP_INFO = "heat_pump_info"

OAUTH2_AUTHORIZE = (
    "https://auth.weheat.nl/auth/realms/Weheat/protocol/openid-connect/auth/"
)
OAUTH2_TOKEN = (
    "https://auth.weheat.nl/auth/realms/Weheat/protocol/openid-connect/token/"
)
API_URL = "https://api.weheat.nl"


UPDATE_INTERVAL = 30

LOGGER: Logger = getLogger(__package__)

DISPLAY_PRECISION_WATTS = 0
DISPLAY_PRECISION_COP = 1
