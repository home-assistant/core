"""Constants for the Smarla integration tests."""

import base64
import json

from homeassistant.const import CONF_ACCESS_TOKEN


def _make_mock_user_input(token_json):
    access_token = base64.b64encode(json.dumps(token_json).encode()).decode()
    return {CONF_ACCESS_TOKEN: access_token}


MOCK_ACCESS_TOKEN_JSON = {
    "refreshToken": "test",
    "appIdentifier": "HA-test",
    "serialNumber": "ABCD",
}
MOCK_USER_INPUT = _make_mock_user_input(MOCK_ACCESS_TOKEN_JSON)

MOCK_ACCESS_TOKEN_JSON_RECONFIGURE = {
    **MOCK_ACCESS_TOKEN_JSON,
    "refreshToken": "reconfiguretest",
}
MOCK_USER_INPUT_RECONFIGURE = _make_mock_user_input(MOCK_ACCESS_TOKEN_JSON_RECONFIGURE)

MOCK_ACCESS_TOKEN_JSON_MISMATCH = {
    **MOCK_ACCESS_TOKEN_JSON_RECONFIGURE,
    "serialNumber": "DCBA",
}
MOCK_USER_INPUT_MISMATCH = _make_mock_user_input(MOCK_ACCESS_TOKEN_JSON_MISMATCH)
