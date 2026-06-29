"""Constants for the Google Health integration."""

from google_health_api.const import HealthApiScope

DOMAIN = "google_health"

OAUTH2_AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH2_TOKEN = "https://oauth2.googleapis.com/token"

OAUTH_SCOPES = [
    HealthApiScope.ACTIVITY_READ,
    HealthApiScope.PROFILE_READ,
    HealthApiScope.MEASUREMENTS_READ,
    "profile",
]
