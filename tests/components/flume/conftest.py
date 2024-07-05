"""Flume test fixtures."""

from collections.abc import Generator
import datetime
from http import HTTPStatus
import json
from unittest.mock import mock_open, patch

import jwt
import pytest
import requests
from requests_mock.mocker import Mocker

from homeassistant.components.flume.const import DOMAIN
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

USER_ID = "test-user-id"
REFRESH_TOKEN = "refresh-token"
TOKEN_URL = "https://api.flumetech.com/oauth/token"
DEVICE_LIST_URL = (
    "https://api.flumetech.com/users/test-user-id/devices?user=true&location=true"
)
BRIDGE_DEVICE = {
    "id": "1234",
    "type": 1,  # Bridge
    "location": {
        "name": "Bridge Location",
    },
    "name": "Flume Bridge",
    "connected": True,
}
SENSOR_DEVICE = {
    "id": "1234",
    "type": 2,  # Sensor
    "location": {
        "name": "Sensor Location",
    },
    "name": "Flume Sensor",
    "connected": True,
}
DEVICE_LIST = [BRIDGE_DEVICE, SENSOR_DEVICE]
NOTIFICATIONS_URL = "https://api.flumetech.com/users/test-user-id/notifications?limit=50&offset=0&sort_direction=ASC"
NOTIFICATION = {
    "id": 111111,
    "device_id": "6248148189204194987",
    "user_id": USER_ID,
    "type": 1,
    "message": "Low Flow Leak triggered at Home. Water has been running for 2 hours averaging 0.43 gallons every minute.",
    "created_datetime": "2020-01-15T16:33:39.000Z",
    "title": "Potential Leak Detected!",
    "read": True,
    "extra": {
        "query": {
            "request_id": "SYSTEM_TRIGGERED_USAGE_ALERT",
            "since_datetime": "2020-01-15 06:33:59",
            "until_datetime": "2020-01-15 08:33:59",
            "tz": "America/Los_Angeles",
            "bucket": "MIN",
            "raw": False,
            "group_multiplier": 2,
            "device_id": ["6248148189204194987"],
        }
    },
    "event_rule": "Low Flow Leak",
}

NOTIFICATIONS_LIST = [NOTIFICATION]


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture to create a config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="test-username",
        unique_id="test-username",
        data={
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_CLIENT_ID: "client_id",
            CONF_CLIENT_SECRET: "client_secret",
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


def encode_access_token() -> str:
    """Encode the payload of the access token."""
    expiration_time = datetime.datetime.now() + datetime.timedelta(hours=12)
    payload = {
        "user_id": USER_ID,
        "exp": int(expiration_time.timestamp()),
    }
    return jwt.encode(payload, key="secret")


@pytest.fixture(name="access_token")
def access_token_fixture(requests_mock: Mocker) -> Generator[None]:
    """Fixture to setup the access token."""
    token_response = {
        "refresh_token": REFRESH_TOKEN,
        "access_token": encode_access_token(),
    }
    requests_mock.register_uri(
        "POST",
        TOKEN_URL,
        status_code=HTTPStatus.OK,
        json={"data": [token_response]},
    )
    with patch("builtins.open", mock_open(read_data=json.dumps(token_response))):
        yield


@pytest.fixture(name="device_list")
def device_list_fixture(requests_mock: Mocker) -> None:
    """Fixture to setup the device list API response access token."""
    requests_mock.register_uri(
        "GET",
        DEVICE_LIST_URL,
        status_code=HTTPStatus.OK,
        json={
            "data": DEVICE_LIST,
        },
    )


@pytest.fixture(name="device_list_timeout")
def device_list_timeout_fixture(requests_mock: Mocker) -> None:
    """Fixture to test a timeout when connecting to the device list url."""
    requests_mock.register_uri(
        "GET",
        DEVICE_LIST_URL,
        exc=requests.exceptions.ConnectTimeout,
    )


@pytest.fixture(name="device_list_unauthorized")
def device_list_unauthorized_fixture(requests_mock: Mocker) -> None:
    """Fixture to test an authorized error from the device list url."""
    requests_mock.register_uri(
        "GET",
        DEVICE_LIST_URL,
        status_code=HTTPStatus.UNAUTHORIZED,
        json={},
    )


@pytest.fixture(name="notifications_list")
def notifications_list_fixture(requests_mock: Mocker) -> None:
    """Fixture to setup the device list API response access token."""
    requests_mock.register_uri(
        "GET",
        NOTIFICATIONS_URL,
        status_code=HTTPStatus.OK,
        json={
            "data": NOTIFICATIONS_LIST,
        },
    )
