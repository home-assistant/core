"""Define fixtures available for all tests."""
import json
import time

import pytest

from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .common import TEST_EMAIL_ADDRESS, TEST_PASSWORD, TEST_TOKEN, TEST_USER_ID

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def config_entry(hass):
    """Config entry version 1 fixture."""
    return MockConfigEntry(
        domain=FLO_DOMAIN,
        data={CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD},
        version=1,
    )


@pytest.fixture
def aioclient_mock_fixture(aioclient_mock):
    """Fixture to provide a aioclient mocker."""
    now = round(time.time())
    # Mocks the login response for flo.
    aioclient_mock.post(
        "https://api.meetflo.com/api/v1/users/auth",
        text=json.dumps(
            {
                "token": TEST_TOKEN,
                "tokenPayload": {
                    "user": {"user_id": TEST_USER_ID, "email": TEST_EMAIL_ADDRESS},
                    "timestamp": now,
                },
                "tokenExpiration": 86400,
                "timeNow": now,
            }
        ),
        headers={"Content-Type": "application/json"},
        status=200,
    )
    # Mocks the device for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/devices/98765",
        text=load_fixture("flo/device_info_response.json"),
        status=200,
        headers={"Content-Type": "application/json"},
    )
    # Mocks the water consumption for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/water/consumption",
        text=load_fixture("flo/water_consumption_info_response.json"),
        status=200,
        headers={"Content-Type": "application/json"},
    )
    # Mocks the location info for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp",
        text=load_fixture("flo/location_info_expand_devices_response.json"),
        status=200,
        headers={"Content-Type": "application/json"},
    )
    # Mocks the user info for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/users/12345abcde",
        text=load_fixture("flo/user_info_expand_locations_response.json"),
        status=200,
        headers={"Content-Type": "application/json"},
        params={"expand": "locations"},
    )
    # Mocks the user info for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/users/12345abcde",
        text=load_fixture("flo/user_info_expand_locations_response.json"),
        status=200,
        headers={"Content-Type": "application/json"},
    )
