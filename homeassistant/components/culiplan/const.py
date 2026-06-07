"""Constants for the Culiplan integration."""

from homeassistant.const import Platform

DOMAIN = "culiplan"

# OAuth client ID for the Home Assistant Core integration. The Culiplan
# backend treats this as a public PKCE client (no client_secret).
OAUTH_CLIENT_ID = "ha-core"
BASE_URL = "https://api.culiplan.com"

OAUTH2_AUTHORIZE = f"{BASE_URL}/api/oauth/authorize"
OAUTH2_TOKEN = f"{BASE_URL}/api/oauth/token"

# OAuth scopes requested for the ha-core client. Must be a subset of the
# allowed scopes registered for "ha-core" in the backend.
OAUTH2_SCOPES: tuple[str, ...] = (
    "calendar:read",
    "todo:read",
    "todo:write",
    "pantry:read",
    "meals:read",
    "shopping:read",
    "shopping:write",
    "recipes:read",
    "profile:read",
    "household:read",
    "openid",
    "offline_access",
)

PLATFORMS: list[Platform] = [Platform.CALENDAR]
