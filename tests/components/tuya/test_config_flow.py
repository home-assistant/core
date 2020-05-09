"""Tests for the Tuya config flow."""
from tuyaha.tuyaapi import TuyaAPIException, TuyaNetException
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.tuya import config_flow
from homeassistant.components.tuya.const import CONF_COUNTRYCODE, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry

USERNAME = "myUsername"
PASSWORD = "myPassword"
COUNTRY_CODE = "1"
TUYA_PLATFORM = "tuya"


@pytest.fixture(name="account")
def mock_controller_login():
    """Mock a successful login."""
    with patch("homeassistant.components.tuya.config_flow.Account", return_value=True):
        yield


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.TuyaConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass, account):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user(
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_COUNTRYCODE: COUNTRY_CODE,
            CONF_PLATFORM: TUYA_PLATFORM,
        }
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_COUNTRYCODE] == COUNTRY_CODE
    assert result["data"][CONF_PLATFORM] == TUYA_PLATFORM


async def test_import(hass, account):
    """Test import step."""
    flow = init_config_flow(hass)

    result = await flow.async_step_import(
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_COUNTRYCODE: COUNTRY_CODE,
            CONF_PLATFORM: TUYA_PLATFORM,
        }
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_COUNTRYCODE] == COUNTRY_CODE
    assert result["data"][CONF_PLATFORM] == TUYA_PLATFORM


async def test_abort_if_already_setup(hass, account):
    """Test we abort if Neato is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_COUNTRYCODE: COUNTRY_CODE,
            CONF_PLATFORM: TUYA_PLATFORM,
        },
    ).add_to_hass(hass)

    # Should fail, config exist (import)
    result = await flow.async_step_import(
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_COUNTRYCODE: COUNTRY_CODE,
            CONF_PLATFORM: TUYA_PLATFORM,
        }
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"

    # Should fail, config exist (flow)
    result = await flow.async_step_user(
        {
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_COUNTRYCODE: COUNTRY_CODE,
            CONF_PLATFORM: TUYA_PLATFORM,
        }
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_abort_on_invalid_credentials(hass):
    """Test when we have invalid credentials."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.tuya.config_flow.Account",
        side_effect=TuyaAPIException(),
    ):
        result = await flow.async_step_user(
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_COUNTRYCODE: COUNTRY_CODE,
                CONF_PLATFORM: TUYA_PLATFORM,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "auth_failed"}

        result = await flow.async_step_import(
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_COUNTRYCODE: COUNTRY_CODE,
                CONF_PLATFORM: TUYA_PLATFORM,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "auth_failed"


async def test_abort_on_connection_error(hass):
    """Test when we have a network error."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.tuya.config_flow.Account",
        side_effect=TuyaNetException(),
    ):
        result = await flow.async_step_user(
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_COUNTRYCODE: COUNTRY_CODE,
                CONF_PLATFORM: TUYA_PLATFORM,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "conn_error"

        result = await flow.async_step_import(
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_COUNTRYCODE: COUNTRY_CODE,
                CONF_PLATFORM: TUYA_PLATFORM,
            }
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "conn_error"
