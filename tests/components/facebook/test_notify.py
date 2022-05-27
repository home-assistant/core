"""The test for the Facebook notify module."""
from http import HTTPStatus

import pytest
import requests_mock

import homeassistant.components.facebook.notify as fb


@pytest.fixture
def facebook():
    """Fixture for facebook."""
    access_token = "page-access-token"
    return fb.FacebookNotificationService(access_token)


async def test_send_simple_message(hass, facebook):
    """Test sending a simple message with success."""
    with requests_mock.Mocker() as mock:
        mock.register_uri(requests_mock.POST, fb.BASE_URL, status_code=HTTPStatus.OK)

        message = "This is just a test"
        target = ["+15555551234"]

        facebook.send_message(message=message, target=target)
        assert mock.called
        assert mock.call_count == 1

        expected_body = {
            "recipient": {"phone_number": target[0]},
            "message": {"text": message},
            "messaging_type": "MESSAGE_TAG",
            "tag": "ACCOUNT_UPDATE",
        }
        assert mock.last_request.json() == expected_body

        expected_params = {"access_token": ["page-access-token"]}
        assert mock.last_request.qs == expected_params


async def test_send_multiple_message(hass, facebook):
    """Test sending a message to multiple targets."""
    with requests_mock.Mocker() as mock:
        mock.register_uri(requests_mock.POST, fb.BASE_URL, status_code=HTTPStatus.OK)

        message = "This is just a test"
        targets = ["+15555551234", "+15555551235"]

        facebook.send_message(message=message, target=targets)
        assert mock.called
        assert mock.call_count == 2

        for idx, target in enumerate(targets):
            request = mock.request_history[idx]
            expected_body = {
                "recipient": {"phone_number": target},
                "message": {"text": message},
                "messaging_type": "MESSAGE_TAG",
                "tag": "ACCOUNT_UPDATE",
            }
            assert request.json() == expected_body

            expected_params = {"access_token": ["page-access-token"]}
            assert request.qs == expected_params


async def test_send_message_attachment(hass, facebook):
    """Test sending a message with a remote attachment."""
    with requests_mock.Mocker() as mock:
        mock.register_uri(requests_mock.POST, fb.BASE_URL, status_code=HTTPStatus.OK)

        message = "This will be thrown away."
        data = {
            "attachment": {
                "type": "image",
                "payload": {"url": "http://www.example.com/image.jpg"},
            }
        }
        target = ["+15555551234"]

        facebook.send_message(message=message, data=data, target=target)
        assert mock.called
        assert mock.call_count == 1

        expected_body = {
            "recipient": {"phone_number": target[0]},
            "message": data,
            "messaging_type": "MESSAGE_TAG",
            "tag": "ACCOUNT_UPDATE",
        }
        assert mock.last_request.json() == expected_body

        expected_params = {"access_token": ["page-access-token"]}
        assert mock.last_request.qs == expected_params

    async def test_send_targetless_message(hass, facebook):
        """Test sending a message without a target."""
        with requests_mock.Mocker() as mock:
            mock.register_uri(
                requests_mock.POST, fb.BASE_URL, status_code=HTTPStatus.OK
            )

            facebook.send_message(message="going nowhere")
            assert not mock.called

    async def test_send_message_with_400(hass, facebook):
        """Test sending a message with a 400 from Facebook."""
        with requests_mock.Mocker() as mock:
            mock.register_uri(
                requests_mock.POST,
                fb.BASE_URL,
                status_code=HTTPStatus.BAD_REQUEST,
                json={
                    "error": {
                        "message": "Invalid OAuth access token.",
                        "type": "OAuthException",
                        "code": 190,
                        "fbtrace_id": "G4Da2pFp2Dp",
                    }
                },
            )
            facebook.send_message(message="nope!", target=["+15555551234"])
            assert mock.called
            assert mock.call_count == 1
