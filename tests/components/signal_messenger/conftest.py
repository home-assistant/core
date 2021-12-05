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
NUMBER_FROM = "+43443434343"
NUMBERS_TO = ["+435565656565"]


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
