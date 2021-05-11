"""Constants for the Geocaching integration."""
from datetime import timedelta

DOMAIN = "geocaching"

OAUTH2_AUTHORIZE_URL = "https://staging.geocaching.com/oauth/authorize.aspx"
OAUTH2_TOKEN_URL = "https://oauth-staging.geocaching.com/token"
API_ENDPOINT_URL = "https://staging.api.groundspeak.com"

UPDATE_INTERVAL = timedelta(hours=1)
