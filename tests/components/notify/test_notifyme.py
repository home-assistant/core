"""The test for the NotifyMe notify module."""
import unittest
import requests_mock

import homeassistant.components.notify.notifyme as notifyme

class TestNotifyMe(unittest.TestCase):
    """Tests for NotifyMe notification service."""

    def setUp(self):
        """Set up test variables."""
        access_token = "dummy-access-token"
        self.notifyme = notifyme.NotifymeNotificationService(access_token)

    @requests_mock.Mocker()
    async def test_send_simple_message(self, mock):
        """Test sending a simple message with success."""
        mock.register_uri(
            requests_mock.POST,
            notifyme.NOTIFYME_API_ENDPOINT,
            status_code=200
        )

        message = "This is a test"

        await self.notifyme.async_send_message(message=message)
        assert mock.called
        assert mock.call_count == 1

        expected_body = {
            "notification": message,
            "accessCode": "dummy-access-token"
        }
        assert mock.last_request.json() == expected_body
