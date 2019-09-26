"""The tests for the notify yessssms platform."""
import unittest
import requests_mock
import homeassistant.components.yessssms.notify as yessssms
from homeassistant.components.yessssms.const import CONF_PROVIDER

from tests.common import get_test_home_assistant
from homeassistant.const import CONF_PASSWORD, CONF_RECIPIENT, CONF_USERNAME


class TestNotifyYesssSMSSetUP(unittest.TestCase):
    """Test the yessssms notify setup."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.login = "06641234567"
        self.passwd = "testpasswd"
        self.recipient = "06501234567"
        self.provider = "yesss"

    def test_unsupported_provider_error(self):
        """Test for unsupported provider."""
        with self.assertLogs(
            "homeassistant.components.yessssms.notify", level="ERROR"
        ) as log_message:
            service = yessssms.get_service(
                get_test_home_assistant,
                {
                    CONF_USERNAME: self.login,
                    CONF_PASSWORD: self.passwd,
                    CONF_PROVIDER: "FantasyMobile",
                },
            )
            self.assertIn("Unknown provider", log_message.output[0])
        self.assertIsNone(service)

    @requests_mock.Mocker()
    def test_login_data(self, mock):
        """Test login data check."""
        mock.register_uri(
            "POST",
            yessssms.YesssSMS("", "", "yesss").get_login_url(),
            status_code=200,
            text="BlaBlaBla<strong>Login nicht erfolgreichBlaBla",
        )
        with self.assertLogs(
            "homeassistant.components.yessssms.notify", level="ERROR"
        ) as log_message:
            service = yessssms.get_service(
                get_test_home_assistant,
                {
                    CONF_USERNAME: self.login,
                    CONF_PASSWORD: self.passwd,
                    CONF_PROVIDER: "yesss",
                },
            )
            self.assertIn("Login data is not valid!", log_message.output[0])
            self.assertIsNone(service)

    @requests_mock.Mocker()
    def test_init_success(self, mock):
        """Test initialization success."""
        # pylint: disable=protected-access
        kontomanager_url = yessssms.YesssSMS("", "", self.provider)._kontomanager
        logout_url = yessssms.YesssSMS("", "", self.provider)._logout_url
        mock.register_uri(
            requests_mock.POST,
            yessssms.YesssSMS("", "", self.provider).get_login_url(),
            status_code=302,
            headers={"location": kontomanager_url},
        )
        mock.register_uri(requests_mock.GET, kontomanager_url, status_code=200)
        mock.register_uri(requests_mock.GET, logout_url, status_code=200)

        with self.assertLogs(
            "homeassistant.components.yessssms.notify", level="DEBUG"
        ) as log_message:
            service = yessssms.get_service(
                get_test_home_assistant,
                {
                    CONF_USERNAME: self.login,
                    CONF_PASSWORD: self.passwd,
                    CONF_PROVIDER: self.provider,
                    CONF_RECIPIENT: self.recipient,
                },
            )
            self.assertIn(
                "Login data for '{}' valid".format(self.provider), log_message.output[0]
            )
            self.assertIsInstance(service, yessssms.YesssSMSNotificationService)
            self.assertIn(
                "initialized; library version: {}".format(service.yesss.version()),
                log_message.output[1],
            )


class TestNotifyYesssSMS(unittest.TestCase):
    """Test the yessssms notify."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        login = "06641234567"
        passwd = "testpasswd"
        recipient = "06501234567"
        client = yessssms.YesssSMS(login, passwd)
        self.yessssms = yessssms.YesssSMSNotificationService(client, recipient)

    @requests_mock.Mocker()
    def test_login_error(self, mock):
        """Test login that fails."""
        mock.register_uri(
            requests_mock.POST,
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=200,
            text="BlaBlaBla<strong>Login nicht erfolgreichBlaBla",
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs("homeassistant.components.yessssms.notify", level="ERROR"):
            self.yessssms.send_message(message)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)

    def test_empty_message_error(self):
        """Test for an empty SMS message error."""
        message = ""
        with self.assertLogs("homeassistant.components.yessssms.notify", level="ERROR"):
            self.yessssms.send_message(message)

    @requests_mock.Mocker()
    def test_error_account_suspended(self, mock):
        """Test login that fails after multiple attempts."""
        mock.register_uri(
            "POST",
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=200,
            text="BlaBlaBla<strong>Login nicht erfolgreichBlaBla",
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs("homeassistant.components.yessssms.notify", level="ERROR"):
            self.yessssms.send_message(message)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)

        mock.register_uri(
            "POST",
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=200,
            text="Wegen 3 ungültigen Login-Versuchen ist Ihr Account für "
            "eine Stunde gesperrt.",
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs("homeassistant.components.yessssms.notify", level="ERROR"):
            self.yessssms.send_message(message)
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 2)

    def test_error_account_suspended_2(self):
        """Test login that fails after multiple attempts."""
        message = "Testing YesssSMS platform :)"
        # pylint: disable=protected-access
        self.yessssms.yesss._suspended = True

        with self.assertLogs(
            "homeassistant.components.yessssms.notify", level="ERROR"
        ) as context:
            self.yessssms.send_message(message)
        self.assertIn("Account is suspended, cannot send SMS.", context.output[0])

    @requests_mock.Mocker()
    def test_send_message(self, mock):
        """Test send message."""
        message = "Testing YesssSMS platform :)"
        mock.register_uri(
            "POST",
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=302,
            # pylint: disable=protected-access
            headers={"location": self.yessssms.yesss._kontomanager},
        )
        # pylint: disable=protected-access
        login = self.yessssms.yesss._logindata["login_rufnummer"]
        mock.register_uri(
            "GET",
            # pylint: disable=protected-access
            self.yessssms.yesss._kontomanager,
            status_code=200,
            text="test..." + login + "</a>",
        )
        mock.register_uri(
            "POST",
            # pylint: disable=protected-access
            self.yessssms.yesss._websms_url,
            status_code=200,
            text="<h1>Ihre SMS wurde erfolgreich verschickt!</h1>",
        )
        mock.register_uri(
            "GET",
            # pylint: disable=protected-access
            self.yessssms.yesss._logout_url,
            status_code=200,
        )

        with self.assertLogs(
            "homeassistant.components.yessssms.notify", level="INFO"
        ) as context:
            self.yessssms.send_message(message)
        self.assertIn("SMS sent", context.output[0])
        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 4)
        self.assertIn(
            mock.last_request.scheme
            + "://"
            + mock.last_request.hostname
            + mock.last_request.path
            + "?"
            + mock.last_request.query,
            # pylint: disable=protected-access
            self.yessssms.yesss._logout_url,
        )

    def test_no_recipient_error(self):
        """Test for missing/empty recipient."""
        message = "Testing YesssSMS platform :)"
        # pylint: disable=protected-access
        self.yessssms._recipient = ""

        with self.assertLogs(
            "homeassistant.components.yessssms.notify", level="ERROR"
        ) as context:
            self.yessssms.send_message(message)

        self.assertIn(
            "You need to provide a recipient for SMS notification", context.output[0]
        )

    @requests_mock.Mocker()
    def test_sms_sending_error(self, mock):
        """Test sms sending error."""
        mock.register_uri(
            "POST",
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            status_code=302,
            # pylint: disable=protected-access
            headers={"location": self.yessssms.yesss._kontomanager},
        )
        # pylint: disable=protected-access
        login = self.yessssms.yesss._logindata["login_rufnummer"]
        mock.register_uri(
            "GET",
            # pylint: disable=protected-access
            self.yessssms.yesss._kontomanager,
            status_code=200,
            text="test..." + login + "</a>",
        )
        mock.register_uri(
            "POST",
            # pylint: disable=protected-access
            self.yessssms.yesss._websms_url,
            status_code=500,
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs(
            "homeassistant.components.yessssms.notify", level="ERROR"
        ) as context:
            self.yessssms.send_message(message)

        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 3)
        self.assertIn("YesssSMS: error sending SMS", context.output[0])

    @requests_mock.Mocker()
    def test_connection_error(self, mock):
        """Test connection error."""
        mock.register_uri(
            "POST",
            # pylint: disable=protected-access
            self.yessssms.yesss._login_url,
            exc=yessssms.YesssSMS.ConnectionError,
        )

        message = "Testing YesssSMS platform :)"

        with self.assertLogs(
            "homeassistant.components.yessssms.notify", level="ERROR"
        ) as context:
            self.yessssms.send_message(message)

        self.assertTrue(mock.called)
        self.assertEqual(mock.call_count, 1)
        self.assertIn("cannot connect to provider", context.output[0])
