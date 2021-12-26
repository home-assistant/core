"""Signal notification test helpers."""
from http import HTTPStatus

from pysignalclirestapi import SignalCliRestApi
import pytest

from homeassistant.components.signal_messenger.notify import SignalNotificationService


@pytest.fixture
def signal_notification_service():
    """Set up signal notification service."""
    recipients = ["+435565656565"]
    number = "+43443434343"
    client = SignalCliRestApi("http://127.0.0.1:8080", number)
    return SignalNotificationService(recipients, client)


SIGNAL_SEND_PATH_SUFIX = "/v2/send"
MESSAGE = "Testing Signal Messenger platform :)"
CONTENT = b"TestContent"
NUMBER_FROM = "+43443434343"
NUMBERS_TO = ["+435565656565"]
URL_ATTACHMENT = "http://127.0.0.1:8080/image.jpg"


@pytest.fixture
def signal_requests_mock(requests_mock):
    """Prepare signal service mock."""
    requests_mock.register_uri(
        "POST",
        "http://127.0.0.1:8080" + SIGNAL_SEND_PATH_SUFIX,
        status_code=HTTPStatus.CREATED,
    )
    requests_mock.register_uri(
        "GET",
        "http://127.0.0.1:8080/v1/about",
        status_code=HTTPStatus.OK,
        json={"versions": ["v1", "v2"]},
    )
    return requests_mock


@pytest.fixture
def signal_attachment_requests_mock(signal_requests_mock):
    """Prepare attachment signal service mock."""
    requests_mock = signal_requests_mock
    requests_mock.register_uri(
        "GET",
        URL_ATTACHMENT,
        status_code=HTTPStatus.OK,
        content=CONTENT,
        headers={"Content-Length": "2048"},
    )
    return requests_mock


@pytest.fixture
def signal_large_attachment_requests_mock(signal_requests_mock):
    """Prepare large attachment signal service mock."""
    requests_mock = signal_requests_mock
    requests_mock.register_uri(
        "GET",
        URL_ATTACHMENT,
        status_code=HTTPStatus.OK,
        content=CONTENT,
        headers={"Content-Length": "52428801"},
    )
    return requests_mock
