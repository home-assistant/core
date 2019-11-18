"""Tests for the iCloud config flow."""
from unittest.mock import patch, MagicMock
import pytest

from pyicloud.exceptions import PyiCloudFailedLoginException

from homeassistant import data_entry_flow
from homeassistant.components.icloud import config_flow

from homeassistant.components.icloud.config_flow import (
    CONF_TRUSTED_DEVICE,
    CONF_VERIFICATION_CODE,
)
from homeassistant.components.icloud.const import (
    DOMAIN,
    CONF_ACCOUNT_NAME,
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_MAX_INTERVAL,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

USERNAME = "username@me.com"
PASSWORD = "password"
ACCOUNT_NAME = "Account name 1 2 3"
ACCOUNT_NAME_FROM_USERNAME = None
MAX_INTERVAL = 15
GPS_ACCURACY_THRESHOLD = 250

TRUSTED_DEVICES = [
    {"deviceType": "SMS", "areaCode": "", "phoneNumber": "*******58", "deviceId": "1"}
]


@pytest.fixture(name="service")
def mock_controller_service():
    """Mock a successful service."""
    with patch("pyicloud.base.PyiCloudSession"):
        with patch("pyicloud.base.PyiCloudService", requires_2fa=True) as service_mock:
            yield service_mock


@pytest.fixture(name="service_with_cookie")
def mock_controller_service_with_cookie():
    """Mock a successful service while already authenticate."""
    with patch("pyicloud.base.PyiCloudSession"):
        with patch("pyicloud.base.PyiCloudService", requires_2fa=False) as service_mock:
            yield service_mock


@pytest.fixture(name="service_send_verification_code_failed")
def mock_controller_service_send_verification_code_failed():
    """Mock a failed service during sending verification code step."""
    with patch("pyicloud.base.PyiCloudSession"):
        with patch(
            "pyicloud.base.PyiCloudService",
            requires_2fa=False,
            trusted_devices=TRUSTED_DEVICES,
        ) as service_mock:
            service_mock.send_verification_code.return_value = False
            yield service_mock


@pytest.fixture(name="service_validate_verification_code_failed")
def mock_controller_service_validate_verification_code_failed():
    """Mock a failed service during validation of verification code step."""
    with patch("pyicloud.base.PyiCloudSession"):
        with patch(
            "pyicloud.base.PyiCloudService",
            requires_2fa=False,
            trusted_devices=TRUSTED_DEVICES,
        ) as service_mock:
            service_mock.send_verification_code.return_value = True
            service_mock.validate_verification_code.return_value = False
            yield service_mock


def init_config_flow(hass: HomeAssistantType, service: MagicMock):
    """Init a configuration flow."""
    flow = config_flow.IcloudFlowHandler()
    flow.hass = hass
    flow.api = service
    return flow


async def test_user(hass, service):
    """Test user config."""
    flow = init_config_flow(hass, service)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE


async def test_user_with_cookie(hass, service_with_cookie):
    """Test user config with presence of a cookie."""
    flow = init_config_flow(hass, service_with_cookie)

    # test with all provided
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCOUNT_NAME] == ACCOUNT_NAME_FROM_USERNAME
    assert result["data"][CONF_MAX_INTERVAL] == DEFAULT_MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == DEFAULT_GPS_ACCURACY_THRESHOLD


async def test_import(hass, service):
    """Test import step."""
    flow = init_config_flow(hass, service)

    # import with username and password
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
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
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "trusted_device"


async def test_import_with_cookie(hass, service_with_cookie):
    """Test import step with presence of a cookie."""
    flow = init_config_flow(hass, service_with_cookie)

    # import with username and password
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
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
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_ACCOUNT_NAME] == ACCOUNT_NAME
    assert result["data"][CONF_MAX_INTERVAL] == MAX_INTERVAL
    assert result["data"][CONF_GPS_ACCURACY_THRESHOLD] == GPS_ACCURACY_THRESHOLD


async def test_abort_if_already_setup(hass):
    """Test we abort if the account is already setup."""
    flow = init_config_flow(hass, None)
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
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "username_exists"

    # Should fail, same USERNAME (flow)
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_USERNAME: "username_exists"}


async def test_abort_on_login_failed(hass):
    """Test when we have errors during login."""
    flow = init_config_flow(hass, None)

    with patch(
        "pyicloud.base.PyiCloudService.authenticate",
        side_effect=PyiCloudFailedLoginException(),
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_USERNAME: "login"}


async def test_trusted_device(hass, service):
    """Test trusted_device step."""
    flow = init_config_flow(hass, service)

    result = await flow.async_step_trusted_device()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE


async def test_trusted_device_success(hass, service):
    """Test trusted_device step success."""
    flow = init_config_flow(hass, service)

    result = await flow.async_step_trusted_device({CONF_TRUSTED_DEVICE: 0})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE


async def test_abort_on_send_verification_code_failed(
    hass, service_send_verification_code_failed
):
    """Test when we have errors during send_verification_code."""
    flow = init_config_flow(hass, service_send_verification_code_failed)

    result = await flow.async_step_trusted_device({CONF_TRUSTED_DEVICE: 0})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {CONF_TRUSTED_DEVICE: "send_verification_code"}


async def test_verification_code(hass):
    """Test verification_code step."""
    flow = init_config_flow(hass, None)

    result = await flow.async_step_verification_code()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == CONF_VERIFICATION_CODE


async def test_abort_on_validate_verification_code_failed(
    hass, service_validate_verification_code_failed
):
    """Test when we have errors during validate_verification_code."""
    flow = init_config_flow(hass, service_validate_verification_code_failed)

    result = await flow.async_step_verification_code({CONF_VERIFICATION_CODE: 0})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == CONF_TRUSTED_DEVICE
    assert result["errors"] == {"base": "validate_verification_code"}
