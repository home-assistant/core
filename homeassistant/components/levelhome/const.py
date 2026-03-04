"""Constants for the Level Lock integration."""

from __future__ import annotations

import os
from typing import TypedDict

DOMAIN = "levelhome"

COMMAND_STATE_TIMEOUT = 15.0  # Seconds to wait for state confirmation after command
STATE_RETRY_MAX_ELAPSED = 60.0  # Max total seconds to retry state reads
STATE_RETRY_INITIAL_DELAY = 2.0  # Initial retry delay in seconds

# Config keys
CONF_OAUTH2_BASE_URL = "oauth2_base_url"
CONF_PARTNER_BASE_URL = "partner_base_url"
CONF_CONTACT_INFO = "contact_info"

# ---------------------------------------------------------------------------
# Environment-based configuration
# Set LEVEL_ENVIRONMENT to "dev", "staging", or "production".
# Defaults to "dev" when the variable is absent.
# ---------------------------------------------------------------------------

LEVEL_ENV_VAR = "LEVEL_ENVIRONMENT"
DEFAULT_ENVIRONMENT = "prod"


class _EnvConfig(TypedDict):
    oauth2_base_url: str
    partner_base_url: str
    client_id: str


ENVIRONMENTS: dict[str, _EnvConfig] = {
    "dev": {
        "oauth2_base_url": "https://oauth2-dev.level.co",
        "partner_base_url": "https://sidewalk-dev.level.co",
        "client_id": "97e9b7976b48481681cb8fe79dc612504a9453688ea549b38014b9202adc5f90",
    },
    "staging": {
        "oauth2_base_url": "https://oauth2-staging.level.co",
        "partner_base_url": "https://sidewalk-staging.level.co",
        "client_id": "deeba2a1cd67445fb4319084d76a739624134ef879d54c83aee5b23ca10abffd",
    },
    "production": {
        "oauth2_base_url": "https://oauth2.level.co",
        "partner_base_url": "https://sidewalk.level.co",
        "client_id": "037e5006b775436499da9284d9f775da9e63f1c868b848eb9c29f788fe248f9b",
    },
}


def get_level_environment() -> str:
    """Return the active Level environment name."""
    env = os.environ.get(LEVEL_ENV_VAR, DEFAULT_ENVIRONMENT).lower()
    if env not in ENVIRONMENTS:
        env = DEFAULT_ENVIRONMENT
    return env


def get_env_config() -> _EnvConfig:
    """Return the configuration dict for the active environment."""
    return ENVIRONMENTS[get_level_environment()]


# Convenience aliases so existing code that references these constants still
# works.  They resolve to the *active* environment's values at import time.
_active = get_env_config()
DEFAULT_OAUTH2_BASE_URL: str = _active["oauth2_base_url"]
DEFAULT_PARTNER_BASE_URL: str = _active["partner_base_url"]
OAUTH2_CLIENT_ID: str = _active["client_id"]

DEVICE_CODE_INITIATE_PATH = "/oauth2/device-code/initiate"
DEVICE_CODE_VERIFY_PATH = "/oauth2/device-code/verify"
DEVICE_CODE_POLL_PATH = "/oauth2/device-code/token"

# API paths
OAUTH2_AUTHORIZE_PATH = "/v1/authorize"
OAUTH2_TOKEN_EXCHANGE_PATH = "/v1/token/exchange"
OAUTH2_OTP_CONFIRM_PATH = "/v1/authenticate/otp/confirm"
OAUTH2_GRANT_PERMISSIONS_ACCEPT_PATH = "/v1/grant-permissions/accept"
PARTNER_OTP_START_PATH = "/v1/oauth2/otp/start"

# Cloud device API paths (resource server)
# These are used by the lock platform to discover devices and control them.
API_LOCKS_LIST_PATH = "/v1/locks"
API_LOCK_STATUS_PATH = "/v1/locks/{lock_id}/status"
API_LOCK_COMMAND_LOCK_PATH = "/v1/locks/{lock_id}/lock"
API_LOCK_COMMAND_UNLOCK_PATH = "/v1/locks/{lock_id}/unlock"
