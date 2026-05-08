"""Constants for the Yoto integration."""

from datetime import timedelta
import logging

DOMAIN = "yoto"

_LOGGER = logging.getLogger(__package__)

# Static identifier passed to YotoManager. The library only uses it for
# diagnostic logs; OAuth tokens are managed by Home Assistant directly.
LIBRARY_CLIENT_ID = "home-assistant"

# Required by Auth0 to mint tokens for the Yoto API.
YOTO_AUDIENCE = "https://api.yotoplay.com"

# Scopes requested for the OAuth2 authorization. The four "auto-included" Yoto
# scopes still have to be listed in the request so the issued token actually
# carries them.
YOTO_SCOPES = [
    "offline_access",
    "family:view",
    "family:devices:view",
    "family:devices:control",
    "family:devices:manage",
    "family:library:view",
    "user:content:view",
    "user:icons:manage",
]

# MQTT delivers real-time updates while a player is online but never pushes a
# disconnect event, so polling is what surfaces the online -> offline transition.
SCAN_INTERVAL = timedelta(minutes=5)

MANUFACTURER = "Yoto"
