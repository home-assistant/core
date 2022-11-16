"""Fixtures for tests."""
from http import HTTPStatus

import pytest

from homeassistant.const import CONTENT_TYPE_JSON

from tests.common import load_fixture


@pytest.fixture
def aioclient_mock_fixture(aioclient_mock) -> None:
    """Fixture to provide a aioclient mocker."""
    aioclient_mock.get(
        "http://1.1.1.1:8080/status.json?show_avail=1",
        text=load_fixture("android_ip_webcam/status_data.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        "http://1.1.1.1:8080/sensors.json",
        text=load_fixture("android_ip_webcam/sensor_data.json"),
        status=HTTPStatus.OK,
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
