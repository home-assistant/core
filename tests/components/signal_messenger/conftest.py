"""Signal notification test helpers."""
from http import HTTPStatus

from pysignalclirestapi import SignalCliRestApi
import pytest
from requests_mock.mocker import Mocker

from homeassistant.components.signal_messenger.notify import SignalNotificationService
from homeassistant.core import HomeAssistant

SIGNAL_SEND_PATH_SUFIX = "/v2/send"
MESSAGE = "Testing Signal Messenger platform :)"
CONTENT = b"TestContent"
NUMBER_FROM = "+43443434343"
NUMBERS_TO = ["+435565656565"]
URL_ATTACHMENT = "http://127.0.0.1:8080/image.jpg"


@pytest.fixture
def signal_notification_service(hass: HomeAssistant) -> SignalNotificationService:
    """Set up signal notification service."""
    hass.config.allowlist_external_urls.add(URL_ATTACHMENT)
    recipients = ["+435565656565"]
    number = "+43443434343"
    client = SignalCliRestApi("http://127.0.0.1:8080", number)
    return SignalNotificationService(hass, recipients, client)


@pytest.fixture
def signal_requests_mock_factory(requests_mock: Mocker) -> Mocker:
    """Create signal service mock from factory."""

    def _signal_requests_mock_factory(
        success_send_result: bool = True, content_length_header: str = None
    ) -> Mocker:
        requests_mock.register_uri(
            "GET",
            "http://127.0.0.1:8080/v1/about",
            status_code=HTTPStatus.OK,
            json={"versions": ["v1", "v2"]},
        )
        if success_send_result:
            requests_mock.register_uri(
                "POST",
                "http://127.0.0.1:8080" + SIGNAL_SEND_PATH_SUFIX,
                status_code=HTTPStatus.CREATED,
            )
        else:
            requests_mock.register_uri(
                "POST",
                "http://127.0.0.1:8080" + SIGNAL_SEND_PATH_SUFIX,
                status_code=HTTPStatus.BAD_REQUEST,
            )
        if content_length_header is not None:
            requests_mock.register_uri(
                "GET",
                URL_ATTACHMENT,
                status_code=HTTPStatus.OK,
                content=CONTENT,
                headers={"Content-Length": content_length_header},
            )
        else:
            requests_mock.register_uri(
                "GET",
                URL_ATTACHMENT,
                status_code=HTTPStatus.OK,
                content=CONTENT,
            )
        return requests_mock

    return _signal_requests_mock_factory
