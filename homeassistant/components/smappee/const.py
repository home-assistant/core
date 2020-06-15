"""Constants for the Smappee Official integration."""

from datetime import timedelta

DOMAIN = "smappee_official"
DATA_CLIENT = "smappee_data"

BASE = "BASE"

SMAPPEE_PLATFORMS = ["sensor", "switch"]

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

AUTHORIZE_URL = "https://app1pub.smappee.net/dev/v1/oauth2/authorize"
TOKEN_URL = "https://app1pub.smappee.net/dev/v3/oauth2/token"
