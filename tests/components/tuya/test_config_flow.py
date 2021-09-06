"""Tests for the Tuya config flow."""
from unittest.mock import MagicMock, Mock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tuya.config_flow import (
    RESULT_AUTH_FAILED,
    RESULT_SINGLE_INSTANCE,
)
from homeassistant.components.tuya.const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_PROJECT_TYPE,
    CONF_USERNAME,
    DOMAIN,
)

from tests.common import MockConfigEntry

MOCK_SMART_HOME_PROJECT_TYPE = 0
MOCK_INDUSTRY_PROJECT_TYPE = 1

MOCK_ACCESS_ID = "myAccessId"
MOCK_ACCESS_SECRET = "myAccessSecret"
MOCK_USERNAME = "myUsername"
MOCK_PASSWORD = "myPassword"
MOCK_COUNTRY_CODE = "1"
MOCK_APP_TYPE = "smartlife"
MOCK_ENDPOINT = "https://openapi-ueaz.tuyaus.com"

TUYA_SMART_HOME_PROJECT_DATA = {
    CONF_PROJECT_TYPE: MOCK_SMART_HOME_PROJECT_TYPE,
}
TUYA_INDUSTRY_PROJECT_DATA = {
    CONF_PROJECT_TYPE: MOCK_INDUSTRY_PROJECT_TYPE,
}

TUYA_INPUT_SMART_HOME_DATA = {
    CONF_ACCESS_ID: MOCK_ACCESS_ID,
    CONF_ACCESS_SECRET: MOCK_ACCESS_SECRET,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_COUNTRY_CODE: MOCK_COUNTRY_CODE,
    CONF_APP_TYPE: MOCK_APP_TYPE,
}

TUYA_INPUT_INDUSTRY_DATA = {
    CONF_ENDPOINT: MOCK_ENDPOINT,
    CONF_ACCESS_ID: MOCK_ACCESS_ID,
    CONF_ACCESS_SECRET: MOCK_ACCESS_SECRET,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
}

TUYA_IMPORT_SMART_HOME_DATA = {
    CONF_PROJECT_TYPE: MOCK_SMART_HOME_PROJECT_TYPE,
    CONF_ACCESS_ID: MOCK_ACCESS_ID,
    CONF_ACCESS_SECRET: MOCK_ACCESS_SECRET,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_COUNTRY_CODE: MOCK_COUNTRY_CODE,
    CONF_APP_TYPE: MOCK_APP_TYPE,
}


TUYA_IMPORT_INDUSTRY_DATA = {
    CONF_PROJECT_TYPE: MOCK_SMART_HOME_PROJECT_TYPE,
    CONF_ENDPOINT: MOCK_ENDPOINT,
    CONF_ACCESS_ID: MOCK_ACCESS_ID,
    CONF_ACCESS_SECRET: MOCK_ACCESS_SECRET,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
}


@pytest.fixture(name="tuya")
def tuya_fixture() -> Mock:
    """Patch libraries."""
    with patch("homeassistant.components.tuya.config_flow.TuyaOpenAPI") as tuya:
        yield tuya


@pytest.fixture(name="tuya_setup", autouse=True)
def tuya_setup_fixture():
    """Mock tuya entry setup."""
    with patch("homeassistant.components.tuya.async_setup_entry", return_value=True):
        yield


async def test_industry_user(hass, tuya):
    """Test industry user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TUYA_INDUSTRY_PROJECT_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "login"

    tuya().login = MagicMock(return_value={"success": True, "errorCode": 1024})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TUYA_INPUT_INDUSTRY_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"][CONF_ACCESS_ID] == MOCK_ACCESS_ID
    assert result["data"][CONF_ACCESS_SECRET] == MOCK_ACCESS_SECRET
    assert result["data"][CONF_USERNAME] == MOCK_USERNAME
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD
    assert not result["result"].unique_id


async def test_smart_home_user(hass, tuya):
    """Test smart home user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TUYA_SMART_HOME_PROJECT_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "login"

    with patch(
        "homeassistant.components.tuya.config_flow.TuyaConfigFlow._try_login",
        return_value={"success": False, "result": ""},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TUYA_INPUT_SMART_HOME_DATA
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "login"

    with patch(
        "homeassistant.components.tuya.config_flow.TuyaConfigFlow._try_login",
        return_value={"success": True, "result": ""},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TUYA_INPUT_SMART_HOME_DATA
        )
        await hass.async_block_till_done()

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == MOCK_USERNAME
        assert result["data"][CONF_ACCESS_ID] == MOCK_ACCESS_ID
        assert result["data"][CONF_ACCESS_SECRET] == MOCK_ACCESS_SECRET
        assert result["data"][CONF_USERNAME] == MOCK_USERNAME
        assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD
        assert result["data"][CONF_COUNTRY_CODE] == MOCK_COUNTRY_CODE
        assert result["data"][CONF_APP_TYPE] == MOCK_APP_TYPE
        assert not result["result"].unique_id

async def test_error_on_invalid_credentials(hass, tuya):
    """Test when we have invalid credentials."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TUYA_INDUSTRY_PROJECT_DATA
    )
    await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "login"

    tuya().login = MagicMock(return_value={"success": False, "errorCode": 1024})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TUYA_INPUT_INDUSTRY_DATA
    )
    await hass.async_block_till_done()

    assert result["errors"]["base"] == RESULT_AUTH_FAILED
