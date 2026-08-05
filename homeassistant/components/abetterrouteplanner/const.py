"""Constants for the A Better Routeplanner integration."""

DOMAIN = "abetterrouteplanner"

OAUTH2_AUTHORIZE = "https://accounts.abetterrouteplanner.com/authorize"
OAUTH2_TOKEN = "https://accounts.abetterrouteplanner.com/token"
OAUTH2_CLIENT_ID = "ha-abrp-integration"

# The ABRP OIDC discovery document advertises the scope as ``oidc`` (not the
# usual ``openid``). ``offline_access`` is required to receive a refresh token.
OAUTH2_SCOPES: list[str] = ["oidc", "profile", "email", "offline_access"]

# Partner API key issued by ABRP (Iternio) for the Home Assistant integration.
ABRP_APP_KEY = "97b4bb90-b8f5-413b-9f28-09789a3777ed"

# Callers must ``int()`` before comparing against ``AbrpVehicle.vehicle_id``:
# ABRP returns an int64 id, but a selector can only store it as a string.
CONF_VEHICLE_IDS = "vehicle_ids"


def signal_new_metric(entry_id: str) -> str:
    """Return the entry-scoped dispatcher signal for first-time metric arrivals."""
    return f"{DOMAIN}_new_metric_{entry_id}"
