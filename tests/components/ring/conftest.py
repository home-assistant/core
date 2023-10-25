"""Configuration for Ring tests."""
import re
from unittest.mock import patch

from firebase_messaging.proto.checkin_pb2 import AndroidCheckinResponse
import pytest
import requests_mock
from ring_doorbell.listen import can_listen

from tests.common import load_fixture, load_json_value_fixture
from tests.components.light.conftest import mock_light_profiles  # noqa: F401
from tests.components.ring.common import load_fixture_as_msg


@pytest.fixture(autouse=True)
def listen_mock():
    """Fixture to mock the push client connect and disconnect."""
    if not can_listen:
        return

    with patch("firebase_messaging.FcmPushClient.start"), patch(
        "firebase_messaging.FcmPushClient.stop"
    ), patch("firebase_messaging.FcmPushClient.is_started", return_value=True):
        yield


@pytest.fixture(name="requests_mock")
def requests_mock_fixture():
    """Fixture to provide a requests mocker."""
    with requests_mock.mock() as mock:
        # Note all devices have an id of 987652, but a different device_id.
        # the device_id is used as our unique_id, but the id is what is sent
        # to the APIs, which is why every mock uses that id.

        # Mocks the response for authenticating
        mock.post(
            "https://oauth.ring.com/oauth/token",
            text=load_fixture("oauth.json", "ring"),
        )
        # Mocks the response for getting the login session
        mock.post(
            "https://api.ring.com/clients_api/session",
            text=load_fixture("session.json", "ring"),
        )
        # Mocks the response for getting all the devices
        mock.get(
            "https://api.ring.com/clients_api/ring_devices",
            text=load_fixture("devices.json", "ring"),
        )
        mock.get(
            "https://api.ring.com/clients_api/dings/active",
            text=load_fixture("ding_active.json", "ring"),
        )
        # Mocks the response for getting the history of a device
        mock.get(
            re.compile(
                r"https:\/\/api\.ring\.com\/clients_api\/doorbots\/\d+\/history"
            ),
            text=load_fixture("doorbots.json", "ring"),
        )
        # Mocks the response for getting the health of a device
        mock.get(
            re.compile(r"https:\/\/api\.ring\.com\/clients_api\/doorbots\/\d+\/health"),
            text=load_fixture("doorboot_health_attrs.json", "ring"),
        )
        # Mocks the response for getting a chimes health
        mock.get(
            re.compile(r"https:\/\/api\.ring\.com\/clients_api\/chimes\/\d+\/health"),
            text=load_fixture("chime_health_attrs.json", "ring"),
        )
        mock.post(
            "https://android.clients.google.com/checkin",
            content=load_fixture_as_msg(
                "android_checkin_response.json", AndroidCheckinResponse
            ).SerializeToString(),
        )
        mock.post(
            "https://android.clients.google.com/c2dm/register3",
            text=load_fixture("gcm_register_response.txt", "ring"),
        )
        mock.post(
            "https://fcm.googleapis.com/fcm/connect/subscribe",
            json=load_json_value_fixture("fcm_register_response.json", "ring"),
        )
        mock.patch(
            "https://api.ring.com/clients_api/device",
            status_code=204,
            content=b"",
        )
        mock.get(
            re.compile(
                r"https:\/\/api\.ring\.com\/clients_api\/dings\/\d+\/share/play"
            ),
            status_code=200,
            json={"url": "http://127.0.0.1/foo"},
        )
        yield mock
