"""Constants for the Geocaching integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

DOMAIN: Final = "geocaching"
LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = timedelta(hours=1)

OAUTH2_AUTHORIZE_URL = "https://staging.geocaching.com/oauth/authorize.aspx"
OAUTH2_TOKEN_URL = "https://oauth-staging.geocaching.com/token"
API_ENDPOINT_URL = "https://staging.api.groundspeak.com"
