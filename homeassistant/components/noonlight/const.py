"""Constants for the Noonlight integration."""

from typing import Final

from homeassistant.const import CONF_API_TOKEN, Platform  # noqa: F401

DOMAIN: Final = "noonlight"

PLATFORMS: Final = [Platform.BINARY_SENSOR]

# --- API ----------------------------------------------------------------------

API_BASE_PROD: Final = "https://api.noonlight.com"
# Sandbox is Noonlight's developer/testing instance. There is no separate
# "dev" hostname — sandbox is the dev environment.
API_BASE_SANDBOX: Final = "https://api-sandbox.noonlight.com"

# Selectable environments. Each named env maps to a base URL above; ``custom``
# lets the user paste an arbitrary base URL (e.g. a private endpoint).
ENV_PRODUCTION: Final = "production"
ENV_SANDBOX: Final = "sandbox"
ENV_CUSTOM: Final = "custom"

ENVIRONMENTS: Final = [ENV_PRODUCTION, ENV_SANDBOX, ENV_CUSTOM]

ENVIRONMENT_BASE_URLS: Final = {
    ENV_PRODUCTION: API_BASE_PROD,
    ENV_SANDBOX: API_BASE_SANDBOX,
}

DEFAULT_ENVIRONMENT: Final = ENV_SANDBOX


def resolve_base_url(environment: str, custom_base_url: str | None) -> str:
    """Resolve a base URL from an environment label + optional override.

    For ``custom`` the override is required; the named environments ignore it.
    Any trailing slash is stripped so path concatenation stays clean.
    """
    if environment == ENV_CUSTOM:
        if not custom_base_url:
            raise ValueError("custom environment requires a base URL")
        return custom_base_url.rstrip("/")
    try:
        return ENVIRONMENT_BASE_URLS[environment].rstrip("/")
    except KeyError as err:
        raise ValueError(f"unknown environment: {environment}") from err


# --- Config entry: data keys --------------------------------------------------

CONF_ENVIRONMENT: Final = "environment"
# Only consulted when ``environment == custom``; holds the override base URL.
CONF_BASE_URL: Final = "base_url"

# --- Reachability probe -------------------------------------------------------

# How often (seconds) to probe Noonlight for reachability + a valid token.
POLL_INTERVAL: Final = 300
# Bogus alarm id used for the side-effect-free probe (GET status → 404 means
# reachable + authorized; 401 means the token is bad). Never creates an alarm.
PROBE_ALARM_ID: Final = "reachability-probe"
