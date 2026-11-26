"""Constants for the A Better Routeplanner integration."""

DOMAIN = "abrp"

OAUTH2_AUTHORIZE = "https://accounts.abetterrouteplanner.com/authorize"
OAUTH2_TOKEN = "https://accounts.abetterrouteplanner.com/token"

# Naming any resource scope drops ABRP's default bundle, so list every one used.
OAUTH2_SCOPES: list[str] = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "veh:read",
    "tlm:read",
    "tlm:write",
]

ABRP_APP_KEY = "97b4bb90-b8f5-413b-9f28-09789a3777ed"
