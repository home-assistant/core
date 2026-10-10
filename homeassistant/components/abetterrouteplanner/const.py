"""Constants for the A Better Routeplanner integration."""

DOMAIN = "abetterrouteplanner"

OAUTH2_AUTHORIZE = "https://accounts.abetterrouteplanner.com/authorize"
OAUTH2_TOKEN = "https://accounts.abetterrouteplanner.com/token"
OAUTH2_CLIENT_ID = "ha-abrp-integration"

OAUTH2_SCOPES: list[str] = ["oidc", "profile", "email", "offline_access"]

ABRP_APP_KEY = "97b4bb90-b8f5-413b-9f28-09789a3777ed"
