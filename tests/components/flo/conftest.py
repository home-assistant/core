"""Define fixtures available for all tests."""

from http import HTTPStatus
import json
import time

import pytest

from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONTENT_TYPE_JSON

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
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=HTTPStatus.OK,
    )
    # Mocks the presence ping response for flo.
    aioclient_mock.post(
        "https://api-gw.meetflo.com/api/v2/presence/me",
        text=load_fixture("flo/ping_response.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
        status=HTTPStatus.OK,
    )
    # Mocks the devices for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/devices/98765",
        text=load_fixture("flo/device_info_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/devices/32839",
        text=load_fixture("flo/device_info_response_detector.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    # Mocks the water consumption for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/water/consumption",
        text=load_fixture("flo/water_consumption_info_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    # Mocks the location info for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp",
        text=load_fixture("flo/location_info_expand_devices_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    # Mocks the user info for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/users/12345abcde",
        text=load_fixture("flo/user_info_expand_locations_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        params={"expand": "locations"},
    )
    # Mocks the user info for flo.
    aioclient_mock.get(
        "https://api-gw.meetflo.com/api/v2/users/12345abcde",
        text=load_fixture("flo/user_info_expand_locations_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    # Mocks the valve open call for flo.
    aioclient_mock.post(
        "https://api-gw.meetflo.com/api/v2/devices/98765",
        text=load_fixture("flo/device_info_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        json={"valve": {"target": "open"}},
    )
    # Mocks the valve close call for flo.
    aioclient_mock.post(
        "https://api-gw.meetflo.com/api/v2/devices/98765",
        text=load_fixture("flo/device_info_response_closed.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        json={"valve": {"target": "closed"}},
    )
    # Mocks the health test call for flo.
    aioclient_mock.post(
        "https://api-gw.meetflo.com/api/v2/devices/98765/healthTest/run",
        text=load_fixture("flo/user_info_expand_locations_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    # Mocks the health test call for flo.
    aioclient_mock.post(
        "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp/systemMode",
        text=load_fixture("flo/user_info_expand_locations_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        json={"systemMode": {"target": "home"}},
    )
    # Mocks the health test call for flo.
    aioclient_mock.post(
        "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp/systemMode",
        text=load_fixture("flo/user_info_expand_locations_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        json={"systemMode": {"target": "away"}},
    )
    # Mocks the health test call for flo.
    aioclient_mock.post(
        "https://api-gw.meetflo.com/api/v2/locations/mmnnoopp/systemMode",
        text=load_fixture("flo/user_info_expand_locations_response.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
        json={
            "systemMode": {
                "target": "sleep",
                "revertMinutes": 120,
                "revertMode": "home",
            }
        },
    )
