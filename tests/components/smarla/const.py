"""Constants for the Smarla integration tests."""

import base64
import json

from homeassistant.components.smarla.const import HOST_DEV
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST

MOCK_ACCESS_TOKEN_JSON = {
    "refreshToken": "test",
    "appIdentifier": "HA-test",
    "serialNumber": "ABCD",
}

MOCK_SERIAL_NUMBER = MOCK_ACCESS_TOKEN_JSON["serialNumber"]

MOCK_ACCESS_TOKEN = base64.b64encode(
    json.dumps(MOCK_ACCESS_TOKEN_JSON).encode()
).decode()

MOCK_USER_INPUT = {
    CONF_ACCESS_TOKEN: MOCK_ACCESS_TOKEN,
    CONF_HOST: HOST_DEV,
}
