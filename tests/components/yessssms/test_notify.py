"""The tests for the notify yessssms platform."""
import logging
import unittest
from unittest.mock import patch

import pytest
import requests_mock

from homeassistant.components.yessssms.const import CONF_PROVIDER
import homeassistant.components.yessssms.notify as yessssms
from homeassistant.const import CONF_PASSWORD, CONF_RECIPIENT, CONF_USERNAME
from homeassistant.setup import async_setup_component


@pytest.fixture(name="config")
def config_data():
    """Set valid config data."""
    config = {
        "notify": {
            "platform": "yessssms",
            "name": "sms",
            CONF_USERNAME: "06641234567",
            CONF_PASSWORD: "secretPassword",
            CONF_RECIPIENT: "06509876543",
            CONF_PROVIDER: "educom",
        }
    }
    return config


@pytest.fixture(name="valid_settings")
def init_valid_settings(hass, config):
    """Initialize component with valid settings."""
    return async_setup_component(hass, "notify", config)


@pytest.fixture(name="invalid_provider_settings")
def init_invalid_provider_settings(hass, config):
    """Set invalid provider data and initialize component."""
    config["notify"][CONF_PROVIDER] = "FantasyMobile"  # invalid provider
    return async_setup_component(hass, "notify", config)


@pytest.fixture(name="invalid_login_data")
def mock_invalid_login_data():
    """Mock invalid login data."""
    path = "homeassistant.components.yessssms.notify.YesssSMS.login_data_valid"
    with patch(path, return_value=False):
        yield


@pytest.fixture(name="valid_login_data")
def mock_valid_login_data():
    """Mock valid login data."""
    path = "homeassistant.components.yessssms.notify.YesssSMS.login_data_valid"
    with patch(path, return_value=True):
        yield


@pytest.fixture(name="connection_error")
def mock_connection_error():
    """Mock a connection error."""
    path = "homeassistant.components.yessssms.notify.YesssSMS.login_data_valid"
    with patch(path, side_effect=yessssms.YesssSMS.ConnectionError()):
        yield


async def test_unsupported_provider_error(hass, caplog, invalid_provider_settings):
    """Test for error on unsupported provider."""
    await invalid_provider_settings
    for record in caplog.records:
        if (
            record.levelname == "ERROR"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert (
                "Unknown provider: provider (fantasymobile) is not known to YesssSMS"
                in record.message
            )
    assert (
        "Unknown provider: provider (fantasymobile) is not known to YesssSMS"
        in caplog.text
    )
    assert not hass.services.has_service("notify", "sms")


async def test_false_login_data_error(hass, caplog, valid_settings, invalid_login_data):
    """Test login data check error."""
    await valid_settings
    assert not hass.services.has_service("notify", "sms")
    for record in caplog.records:
        if (
            record.levelname == "ERROR"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert (
                "Login data is not valid! Please double check your login data at"
                in record.message
            )


async def test_init_success(hass, caplog, valid_settings, valid_login_data):
    """Test for successful init of yessssms."""
    caplog.set_level(logging.DEBUG)
    await valid_settings
    assert hass.services.has_service("notify", "sms")
    messages = []
    for record in caplog.records:
        if (
            record.levelname == "DEBUG"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            messages.append(record.message)
    assert "Login data for 'educom' valid" in messages[0]
    assert (
        "initialized; library version: {}".format(yessssms.YesssSMS("", "").version())
        in messages[1]
    )


async def test_connection_error_on_init(hass, caplog, valid_settings, connection_error):
    """Test for connection error on init."""
    caplog.set_level(logging.DEBUG)
    await valid_settings
    assert hass.services.has_service("notify", "sms")
    for record in caplog.records:
        if (
            record.levelname == "WARNING"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert (
                "Connection Error, could not verify login data for 'educom'"
                in record.message
            )
    for record in caplog.records:
        if (
            record.levelname == "DEBUG"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert (
                "initialized; library version: {}".format(
                    yessssms.YesssSMS("", "").version()
                )
                in record.message
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
            text=f"test...{login}</a>",
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
            text=f"test...{login}</a>",
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
