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
# Set LEVEL_ENVIRONMENT to "dev", "stage", or "production".
# Set LEVEL_PARTNER to "joshai", "crestron", or "homeassistant" to pick the
# OAuth2 client ID. Both default to JoshAI / production when absent.
# ---------------------------------------------------------------------------

LEVEL_ENV_VAR = "LEVEL_ENVIRONMENT"
LEVEL_PARTNER_VAR = "LEVEL_PARTNER"
DEFAULT_ENVIRONMENT = "production"
DEFAULT_PARTNER = "joshai"


class _EnvConfig(TypedDict):
    oauth2_base_url: str
    partner_base_url: str
    client_id: str


_ENV_URLS: dict[str, dict[str, str]] = {
    "dev": {
        "oauth2_base_url": "https://oauth2-dev.level.co",
        "partner_base_url": "https://sidewalk-dev.level.co",
    },
    "stage": {
        "oauth2_base_url": "https://oauth2-stage.level.co",
        "partner_base_url": "https://sidewalk-stage.level.co",
    },
    "production": {
        "oauth2_base_url": "https://oauth2.level.co",
        "partner_base_url": "https://sidewalk.level.co",
    },
}

_PARTNER_CLIENT_IDS: dict[str, dict[str, str]] = {
    "joshai": {
        "dev": "97e9b7976b48481681cb8fe79dc612504a9453688ea549b38014b9202adc5f90",
        "stage": "deeba2a1cd67445fb4319084d76a739624134ef879d54c83aee5b23ca10abffd",
        "production": "037e5006b775436499da9284d9f775da9e63f1c868b848eb9c29f788fe248f9b",
    },
    "crestron": {
        "dev": "6a1d5a61a6464f0b9f9a66fde426cf3a",
        "stage": "acdf037503d14dba948d36ae2e68693c",
        "production": "c22cb672451e40c0a169bf2d8e9ba583",
    },
    "homeassistant": {
        "dev": "a407399f037446adb50224db85bd4b37",
        "stage": "6638a058322d4c09908f43f1fb15173c",
        "production": "bab5044a2222422680d1d21c188b628c",
    },
}


def get_level_environment() -> str:
    """Return the active Level environment name."""
    env = os.environ.get(LEVEL_ENV_VAR, DEFAULT_ENVIRONMENT).lower()
    if env not in _ENV_URLS:
        env = DEFAULT_ENVIRONMENT
    return env


def get_level_partner() -> str:
    """Return the active Level partner name."""
    partner = os.environ.get(LEVEL_PARTNER_VAR, DEFAULT_PARTNER).lower()
    if partner not in _PARTNER_CLIENT_IDS:
        partner = DEFAULT_PARTNER
    return partner


def get_env_config() -> _EnvConfig:
    """Return the configuration dict for the active environment and partner."""
    env = get_level_environment()
    partner = get_level_partner()
    return {
        "oauth2_base_url": _ENV_URLS[env]["oauth2_base_url"],
        "partner_base_url": _ENV_URLS[env]["partner_base_url"],
        "client_id": _PARTNER_CLIENT_IDS[partner][env],
    }


DEFAULT_PARTNER_BASE_URL = _ENV_URLS[DEFAULT_ENVIRONMENT]["partner_base_url"]

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
