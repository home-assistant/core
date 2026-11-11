"""Constants for the Remootio integration."""

DOMAIN = "remootio"

CONF_API_SECRET_KEY = "api_secret_key"
CONF_API_AUTH_KEY = "api_auth_key"


def device_name(serial: str) -> str:
    """Return the default name for a Remootio device."""
    return f"Remootio device ({serial})"
