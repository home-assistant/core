"""The tests for the notify sinch_sms platform."""
import unittest
import requests_mock
import homeassistant.components.sinch_sms.notify as sinch_sms


class TestNotifySinchSMS(unittest.TestCase):
    """Test the sinch_sms notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""

        config = {
            sinch_sms.CONF_API_KEY: "myapikey",
            sinch_sms.CONF_RECIPIENT: "+4699999999",
            sinch_sms.CONF_SERVICE_PLAN_ID: "myID",
            sinch_sms.CONF_FROM_NUMBER: "4699999999",
        }

        self.sinch_sms = sinch_sms.SinchNotificationService(config)

    @requests_mock.Mocker()
    def test_send_message(self, mock):
        """Test send message."""

        mock.register_uri(
            requests_mock.POST,
            "https://sms.api.sinch.com/xms/v1/myID/batches",
            complete_qs=True,
            status_code=200,
            json={"mock_response": "Ok"},
        )

        message = "My Message from Sinch!"

        with self.assertLogs(
            "homeassistant.components.sinch_sms.notify", level="INFO"
        ) as context:
            self.sinch_sms.send_message(message)

        self.assertIn("Successfully sent sms!", context.output[0])
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)
