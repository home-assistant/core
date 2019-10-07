"""Tests for the iCloud config flow."""
import pytest
import logging
from unittest.mock import patch
from pyicloud.exceptions import PyiCloudFailedLoginException

from homeassistant import data_entry_flow
from homeassistant.components.icloud import config_flow
from homeassistant.components.icloud.config_flow import CONF_TRUSTED_DEVICE
from homeassistant.components.icloud.const import (
    DOMAIN,
    CONF_ACCOUNT_NAME,
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_MAX_INTERVAL,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

USERNAME = "username@me.com"
PASSWORD = "password"
ACCOUNT_NAME = "Account name 1 2 3"
ACCOUNT_NAME_FROM_USERNAME = "username"
MAX_INTERVAL = 15
GPS_ACCURACY_THRESHOLD = 250


@pytest.fixture(name="session")
def mock_controller_session():
    """Mock a successful session."""
    with patch("pyicloud.base.PyiCloudSession"):
        yield


@pytest.fixture(name="service")
def mock_controller_service():
    """Mock a successful service."""
    with patch("pyicloud.base.PyiCloudService") as mock_service:
        mock_service.return_value.authenticate.return_value = None
        mock_service.return_value.requires_2fa.return_value = True
        mock_service.return_value.send_verification_code.return_value = True
        mock_service.return_value.validate_verification_code.return_value = True
        yield mock_service


@pytest.fixture(name="service_with_cookie")
def mock_controller_service_with_cookie():
    """Mock a successful service while already authenticate."""
    with patch("pyicloud.base.PyiCloudService") as mock_service:
        mock_service.return_value.authenticate.return_value = None
        mock_service.return_value.requires_2fa.return_value = False
        mock_service.return_value.send_verification_code.return_value = False
        mock_service.return_value.validate_verification_code.return_value = False
        yield mock_service


@pytest.fixture(name="service_send_verification_code_failed")
def mock_controller_service_send_verification_code_failed():
    """Mock a failed service during sending verification code step."""
    with patch("pyicloud.base.PyiCloudService") as mock_service:
        mock_service.return_value.authenticate.return_value = None
        mock_service.return_value.requires_2fa.return_value = False
        mock_service.return_value.send_verification_code.return_value = False
        mock_service.return_value.validate_verification_code.return_value = False
        yield mock_service


@pytest.fixture(name="service_validate_verification_code_failed")
def mock_controller_service_validate_verification_code_failed():
    """Mock a failed service during validation of verification code step."""
    with patch("pyicloud.base.PyiCloudService") as mock_service:
        mock_service.return_value.authenticate.return_value = None
        mock_service.return_value.requires_2fa.return_value = False
        mock_service.return_value.send_verification_code.return_value = True
        mock_service.return_value.validate_verification_code.return_value = False
        yield mock_service


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.IcloudFlowHandler()
    flow.hass = hass
    return flow


async def test_user(hass, session, service):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "trusted_device"


async def test_user_with_cookie(hass, session, service_with_cookie):
    """Test user config with presence of a cookie."""
    flow = init_config_flow(hass)

    # test with all provided
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    _LOGGER.info(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCOUNT_NAME] == ACCOUNT_NAME_FROM_USERNAME
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD


async def test_import(hass, session, service):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with username and password
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    _LOGGER.info(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "trusted_device"

    # import with all
    result = await flow.async_step_import(
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NAME: ACCOUNT_NAME,
            CONF_MAX_INTERVAL: MAX_INTERVAL,
            CONF_GPS_ACCURACY_THRESHOLD: GPS_ACCURACY_THRESHOLD,
        }
    )
    _LOGGER.info(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "trusted_device"


async def test_import_with_cookie(hass, session, service_with_cookie):
    """Test import step with presence of a cookie."""
    flow = init_config_flow(hass)

    # import with username and password
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    _LOGGER.info(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCOUNT_NAME] == ACCOUNT_NAME_FROM_USERNAME
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD

    # import with all
    result = await flow.async_step_import(
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NAME: ACCOUNT_NAME,
            CONF_MAX_INTERVAL: MAX_INTERVAL,
            CONF_GPS_ACCURACY_THRESHOLD: GPS_ACCURACY_THRESHOLD,
        }
    )
    _LOGGER.info(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCOUNT_NAME] == ACCOUNT_NAME
    assert result["data"][CONF_MAX_INTERVAL] == MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == GPS_ACCURACY_THRESHOLD


async def test_abort_if_already_setup(hass):
    """Test we abort if the account is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    ).add_to_hass(hass)

    # Should fail, same USERNAME (import)
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "username_exists"

    # Should fail, same ACCOUNT_NAME (import)
    result = await flow.async_step_import(
        {
            CONF_USERNAME: "other_username@icloud.com",
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NAME: ACCOUNT_NAME_FROM_USERNAME,
        }
    )
    _LOGGER.info(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "username_exists"

    # Should fail, same USERNAME (flow)
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_USERNAME: "username_exists"}

    # Should fail, same ACCOUNT_NAME (flow)
    result = await flow.async_step_user(
        {
            CONF_USERNAME: "other_username@icloud.com",
            CONF_PASSWORD: PASSWORD,
            CONF_ACCOUNT_NAME: ACCOUNT_NAME_FROM_USERNAME,
        }
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["reason"] == {CONF_USERNAME: "username_exists"}


async def test_abort_on_login_failed(hass):
    """Test when we have errors during login."""
    flow = init_config_flow(hass)

    with patch(
        "pyicloud.base.PyiCloudService.authenticate",
        side_effect=PyiCloudFailedLoginException(),
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_USERNAME: "login"}


async def test_abort_on_send_verification_code_failed(
    hass, session, service_send_verification_code_failed
):
    """Test when we have errors during send_verification_code."""
    flow = init_config_flow(hass)

    result = await flow.async_step_trusted_device(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    _LOGGER.info(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_TRUSTED_DEVICE: "send_verification_code"}


async def test_abort_on_validate_verification_code_failed(
    hass, session, service_validate_verification_code_failed
):
    """Test when we have errors during validate_verification_code."""
    flow = init_config_flow(hass)

    result = await flow.async_step_verification_code(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    _LOGGER.info(result)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "validate_verification_code"}
