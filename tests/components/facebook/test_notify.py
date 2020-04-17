"""The test for the Facebook notify module."""
import unittest

import requests_mock

# import homeassistant.components.facebook as facebook
import homeassistant.components.facebook.notify as facebook


class TestFacebook(unittest.TestCase):
    """Tests for Facebook notification service."""

    def setUp(self):
        """Set up test variables."""
        access_token = "page-access-token"
        self.facebook = facebook.FacebookNotificationService(access_token)

    @requests_mock.Mocker()
    def test_send_simple_message(self, mock):
        """Test sending a simple message with success."""
        mock.register_uri(requests_mock.POST, facebook.BASE_URL, status_code=200)

        message = "This is just a test"
        target = ["+15555551234"]

        self.facebook.send_message(message=message, target=target)
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

    @requests_mock.Mocker()
    def test_sending_multiple_messages(self, mock):
        """Test sending a message to multiple targets."""
        mock.register_uri(requests_mock.POST, facebook.BASE_URL, status_code=200)

        message = "This is just a test"
        targets = ["+15555551234", "+15555551235"]

        self.facebook.send_message(message=message, target=targets)
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

    @requests_mock.Mocker()
    def test_send_message_attachment(self, mock):
        """Test sending a message with a remote attachment."""
        mock.register_uri(requests_mock.POST, facebook.BASE_URL, status_code=200)

        message = "This will be thrown away."
        data = {
            "attachment": {
                "type": "image",
                "payload": {"url": "http://www.example.com/image.jpg"},
            }
        }
        target = ["+15555551234"]

        self.facebook.send_message(message=message, data=data, target=target)
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

    @requests_mock.Mocker()
    def test_send_targetless_message(self, mock):
        """Test sending a message without a target."""
        mock.register_uri(requests_mock.POST, facebook.BASE_URL, status_code=200)

        self.facebook.send_message(message="going nowhere")
        assert not mock.called

    @requests_mock.Mocker()
    def test_send_message_with_400(self, mock):
        """Test sending a message with a 400 from Facebook."""
        mock.register_uri(
            requests_mock.POST,
            facebook.BASE_URL,
            status_code=400,
            json={
                "error": {
                    "message": "Invalid OAuth access token.",
                    "type": "OAuthException",
                    "code": 190,
                    "fbtrace_id": "G4Da2pFp2Dp",
                }
            },
        )
        self.facebook.send_message(message="nope!", target=["+15555551234"])
        assert mock.called
        assert mock.call_count == 1
