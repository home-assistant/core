"""Constants for the GridX integration."""

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "gridx"

LOGGER = logging.getLogger(__package__)

API_BASE_URL: Final = "https://api.gridx.de"

# Only the E.ON Home realm remains; the Viessmann realm was shut down end of 2025.
LOGIN_URL: Final = "https://gridx.eu.auth0.com/oauth/token"
LOGIN_GRANT_TYPE: Final = "http://auth0.com/oauth/grant-type/password-realm"
LOGIN_AUDIENCE: Final = "my.gridx"
LOGIN_CLIENT_ID: Final = "mG0Phmo7DmnvAqO7p6B0WOYBODppY3cc"
LOGIN_SCOPE: Final = "email openid offline_access"
LOGIN_REALM: Final = "eon-home-authentication-db"

LIVE_UPDATE_INTERVAL = timedelta(seconds=30)
