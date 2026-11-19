"""Constants for the Untappd integration."""

from datetime import timedelta
import logging

DOMAIN = "untappd"
LOGGER = logging.getLogger(__package__)

# Untappd allows 100 API calls per hour per user, and every update makes two.
SCAN_INTERVAL = timedelta(minutes=15)

OAUTH2_AUTHORIZE = "https://untappd.com/oauth/authenticate/"
OAUTH2_TOKEN = "https://untappd.com/oauth/authorize/"

# Untappd access tokens do not expire.
TOKEN_EXPIRES_IN = 10 * 365 * 24 * 60 * 60
