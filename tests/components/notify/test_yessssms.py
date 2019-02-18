"""The tests for the notify yessssms platform."""
import unittest
import requests_mock
from homeassistant.components.notify import yessssms


class TestNotifyYesssSMS(unittest.TestCase):
    """Test the yessssms notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        login = "06641234567"
        passwd = "testpasswd"
        recipient = "06501234567"
        self.yessssms = yessssms.YesssSMSNotificationService(
            login, passwd, recipient)

    @requests_mock.Mocker()
    def test_login_error(self, mock):
        """Test login that fails."""
        mock.register_uri(
            requests_mock.POST,
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=200,
            text="BlaBlaBla<strong>Login nicht erfolgreichBlaBla"
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs("homeassistant.components.notify",
                             level='ERROR'):
            self.yessssms.send_message(message)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)

    def test_empty_message_error(self):
        """Test for an empty SMS message error."""
        message = ""
        with self.assertLogs("homeassistant.components.notify",
                             level='ERROR'):
            self.yessssms.send_message(message)

    @requests_mock.Mocker()
    def test_error_account_suspended(self, mock):
        """Test login that fails after multiple attempts."""
        mock.register_uri(
            'POST',
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=200,
            text="BlaBlaBla<strong>Login nicht erfolgreichBlaBla"
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs("homeassistant.components.notify",
                             level='ERROR'):
            self.yessssms.send_message(message)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)

        mock.register_uri(
            'POST',
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=200,
            text="Wegen 3 ungültigen Login-Versuchen ist Ihr Account für "
                 "eine Stunde gesperrt."
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs("homeassistant.components.notify",
                             level='ERROR'):
            self.yessssms.send_message(message)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 2)

    def test_error_account_suspended_2(self):
        """Test login that fails after multiple attempts."""
        message = "Testing YesssSMS platform :)"
        # pylint: disable=protected-access
        self.yessssms.yesss._suspended = True

        with self.assertLogs("homeassistant.components.notify",
                             level='ERROR') as context:
            self.yessssms.send_message(message)
        self.assertIn("Account is suspended, cannot send SMS.",
                      context.output[0])

    @requests_mock.Mocker()
    def test_send_message(self, mock):
        """Test send message."""
        message = "Testing YesssSMS platform :)"
        mock.register_uri(
            'POST',
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=302,
            # pylint: disable=protected-access
            headers={'location': self.yessssms.yesss._kontomanager}
        )
        # pylint: disable=protected-access
        login = self.yessssms.yesss._logindata['login_rufnummer']
        mock.register_uri(
            'GET',
            # pylint: disable=protected-access
            self.yessssms.yesss._kontomanager,
            status_code=200,
            text="test..." + login + "</a>"
        )
        mock.register_uri(
            'POST',
            # pylint: disable=protected-access
            self.yessssms.yesss._websms_url,
            status_code=200,
            text="<h1>Ihre SMS wurde erfolgreich verschickt!</h1>"
        )
        mock.register_uri(
            'GET',
            # pylint: disable=protected-access
            self.yessssms.yesss._logout_url,
            status_code=200,
        )

        with self.assertLogs("homeassistant.components.notify",
                             level='INFO') as context:
            self.yessssms.send_message(message)
        self.assertIn("SMS sent", context.output[0])
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 4)
        self.assertIn(mock.last_request.scheme + "://" +
                      mock.last_request.hostname +
                      mock.last_request.path + "?" +
                      mock.last_request.query,
                      # pylint: disable=protected-access
                      self.yessssms.yesss._logout_url)

    def test_no_recipient_error(self):
        """Test for missing/empty recipient."""
        message = "Testing YesssSMS platform :)"
        # pylint: disable=protected-access
        self.yessssms._recipient = ""

        with self.assertLogs("homeassistant.components.notify",
                             level='ERROR') as context:
            self.yessssms.send_message(message)

        self.assertIn("You need to provide a recipient for SMS notification",
                      context.output[0])

    @requests_mock.Mocker()
    def test_sms_sending_error(self, mock):
        """Test sms sending error."""
        mock.register_uri(
            'POST',
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=302,
            # pylint: disable=protected-access
            headers={'location': self.yessssms.yesss._kontomanager}
        )
        # pylint: disable=protected-access
        login = self.yessssms.yesss._logindata['login_rufnummer']
        mock.register_uri(
            'GET',
            # pylint: disable=protected-access
            self.yessssms.yesss._kontomanager,
            status_code=200,
            text="test..." + login + "</a>"
        )
        mock.register_uri(
            'POST',
            # pylint: disable=protected-access
            self.yessssms.yesss._websms_url,
            status_code=500
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs("homeassistant.components.notify",
                             level='ERROR') as context:
            self.yessssms.send_message(message)

        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 3)
        self.assertIn("YesssSMS: error sending SMS", context.output[0])

    @requests_mock.Mocker()
    def test_connection_error(self, mock):
        """Test connection error."""
        mock.register_uri(
            'POST',
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            exc=ConnectionError
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs("homeassistant.components.notify",
                             level='ERROR') as context:
            self.yessssms.send_message(message)

        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)
        self.assertIn("unable to connect", context.output[0])
