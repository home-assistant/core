"""Constants for the Jellyfin integration tests."""

from typing import Final

from jellyfin_apiclient_python.connection_manager import CONNECTION_STATE

TEST_URL: Final = "https://example.com"
TEST_USERNAME: Final = "test-username"
TEST_PASSWORD: Final = "test-password"

MOCK_SUCCESFUL_CONNECTION_STATE: Final = {"State": CONNECTION_STATE["ServerSignIn"]}
MOCK_SUCCESFUL_LOGIN_RESPONSE: Final = {"AccessToken": "Test"}

MOCK_UNSUCCESFUL_CONNECTION_STATE: Final = {"State": CONNECTION_STATE["Unavailable"]}
MOCK_UNSUCCESFUL_LOGIN_RESPONSE: Final = {""}

MOCK_USER_SETTINGS: Final = {"Id": "123"}
