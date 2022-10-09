"""Tests for the jellyfin integration."""
import json

from tests.common import load_fixture

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
