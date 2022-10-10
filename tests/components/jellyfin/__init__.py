"""Tests for the jellyfin integration."""
import json
from typing import Any

from tests.common import load_fixture


def load_json_fixture(filename: str) -> Any:
    """Load JSON fixture on-demand."""
    return json.loads(load_fixture(f"jellyfin/{filename}"))


MOCK_AUTH_CONNECT_ADDRESS_SUCCESS = json.loads(
    load_fixture("jellyfin/auth-connect-address.json")
)

MOCK_AUTH_CONNECT_ADDRESS_FAILURE = json.loads(
    load_fixture("jellyfin/auth-connect-address-failure.json")
)

MOCK_AUTH_LOGIN_SUCCESS = json.loads(load_fixture("jellyfin/auth-login.json"))

MOCK_AUTH_LOGIN_FAILURE = json.loads(load_fixture("jellyfin/auth-login-failure.json"))

MOCK_GET_USER_SETTINGS_SUCCESS = json.loads(
    load_fixture("jellyfin/get-user-settings.json")
)
