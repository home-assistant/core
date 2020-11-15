"""The tests for the notify yessssms platform."""
import logging

import pytest

from homeassistant.components.yessssms.const import CONF_PROVIDER
import homeassistant.components.yessssms.notify as yessssms
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_USERNAME,
    HTTP_INTERNAL_SERVER_ERROR,
)
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


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


@pytest.fixture(name="yessssms")
def yessssms_init():
    """Set up things to be run when tests are started."""
    login = "06641234567"
    passwd = "testpasswd"
    recipient = "06501234567"
    client = yessssms.YesssSMS(login, passwd)
    return yessssms.YesssSMSNotificationService(client, recipient)


async def test_login_error(yessssms, requests_mock, caplog):
    """Test login that fails."""
    requests_mock.post(
        # pylint: disable=protected-access
        yessssms.yesss._login_url,
        status_code=200,
        text="BlaBlaBla<strong>Login nicht erfolgreichBlaBla",
    )

    message = "Testing YesssSMS platform :)"

    with caplog.at_level(logging.ERROR):
        yessssms.send_message(message)
    assert requests_mock.called is True
    assert requests_mock.call_count == 1


async def test_empty_message_error(yessssms, caplog):
    """Test for an empty SMS message error."""
    message = ""
    with caplog.at_level(logging.ERROR):
        yessssms.send_message(message)

    for record in caplog.records:
        if (
            record.levelname == "ERROR"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert "Cannot send empty SMS message" in record.message


async def test_error_account_suspended(yessssms, requests_mock, caplog):
    """Test login that fails after multiple attempts."""
    requests_mock.post(
        # pylint: disable=protected-access
        yessssms.yesss._login_url,
        status_code=200,
        text="BlaBlaBla<strong>Login nicht erfolgreichBlaBla",
    )

    message = "Testing YesssSMS platform :)"

    yessssms.send_message(message)
    assert requests_mock.called is True
    assert requests_mock.call_count == 1

    requests_mock.post(
        # pylint: disable=protected-access
        yessssms.yesss._login_url,
        status_code=200,
        text="Wegen 3 ungültigen Login-Versuchen ist Ihr Account für "
        "eine Stunde gesperrt.",
    )

    message = "Testing YesssSMS platform :)"

    with caplog.at_level(logging.ERROR):
        yessssms.send_message(message)
    assert requests_mock.called is True
    assert requests_mock.call_count == 2


async def test_error_account_suspended_2(yessssms, caplog):
    """Test login that fails after multiple attempts."""
    message = "Testing YesssSMS platform :)"
    # pylint: disable=protected-access
    yessssms.yesss._suspended = True

    with caplog.at_level(logging.ERROR):
        yessssms.send_message(message)
    for record in caplog.records:
        if (
            record.levelname == "ERROR"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert "Account is suspended, cannot send SMS." in record.message


async def test_send_message(yessssms, requests_mock, caplog):
    """Test send message."""
    message = "Testing YesssSMS platform :)"
    requests_mock.post(
        # pylint: disable=protected-access
        yessssms.yesss._login_url,
        status_code=302,
        # pylint: disable=protected-access
        headers={"location": yessssms.yesss._kontomanager},
    )
    # pylint: disable=protected-access
    login = yessssms.yesss._logindata["login_rufnummer"]
    requests_mock.get(
        # pylint: disable=protected-access
        yessssms.yesss._kontomanager,
        status_code=200,
        text=f"test...{login}</a>",
    )
    requests_mock.post(
        # pylint: disable=protected-access
        yessssms.yesss._websms_url,
        status_code=200,
        text="<h1>Ihre SMS wurde erfolgreich verschickt!</h1>",
    )
    requests_mock.get(
        # pylint: disable=protected-access
        yessssms.yesss._logout_url,
        status_code=200,
    )

    with caplog.at_level(logging.INFO):
        yessssms.send_message(message)
    for record in caplog.records:
        if (
            record.levelname == "INFO"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert "SMS sent" in record.message

    assert requests_mock.called is True
    assert requests_mock.call_count == 4
    assert (
        requests_mock.last_request.scheme
        + "://"
        + requests_mock.last_request.hostname
        + requests_mock.last_request.path
        + "?"
        + requests_mock.last_request.query
    ) in yessssms.yesss._logout_url  # pylint: disable=protected-access


async def test_no_recipient_error(yessssms, caplog):
    """Test for missing/empty recipient."""
    message = "Testing YesssSMS platform :)"
    # pylint: disable=protected-access
    yessssms._recipient = ""

    with caplog.at_level(logging.ERROR):
        yessssms.send_message(message)
    for record in caplog.records:
        if (
            record.levelname == "ERROR"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert (
                "You need to provide a recipient for SMS notification" in record.message
            )


async def test_sms_sending_error(yessssms, requests_mock, caplog):
    """Test sms sending error."""
    requests_mock.post(
        # pylint: disable=protected-access
        yessssms.yesss._login_url,
        status_code=302,
        # pylint: disable=protected-access
        headers={"location": yessssms.yesss._kontomanager},
    )
    # pylint: disable=protected-access
    login = yessssms.yesss._logindata["login_rufnummer"]
    requests_mock.get(
        # pylint: disable=protected-access
        yessssms.yesss._kontomanager,
        status_code=200,
        text=f"test...{login}</a>",
    )
    requests_mock.post(
        # pylint: disable=protected-access
        yessssms.yesss._websms_url,
        status_code=HTTP_INTERNAL_SERVER_ERROR,
    )

    message = "Testing YesssSMS platform :)"

    with caplog.at_level(logging.ERROR):
        yessssms.send_message(message)

    assert requests_mock.called is True
    assert requests_mock.call_count == 3
    for record in caplog.records:
        if (
            record.levelname == "ERROR"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert "YesssSMS: error sending SMS" in record.message


async def test_connection_error(yessssms, requests_mock, caplog):
    """Test connection error."""
    requests_mock.post(
        # pylint: disable=protected-access
        yessssms.yesss._login_url,
        exc=yessssms.yesss.ConnectionError,
    )

    message = "Testing YesssSMS platform :)"

    with caplog.at_level(logging.ERROR):
        yessssms.send_message(message)

    assert requests_mock.called is True
    assert requests_mock.call_count == 1
    for record in caplog.records:
        if (
            record.levelname == "ERROR"
            and record.name == "homeassistant.components.yessssms.notify"
        ):
            assert "cannot connect to provider" in record.message
