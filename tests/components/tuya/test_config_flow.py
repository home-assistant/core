"""Tests for the Tuya config flow."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from tuya_iot import TuyaCloudOpenAPIEndpoint

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tuya.const import (
    CONF_ACCESS_ID,
    CONF_ACCESS_SECRET,
    CONF_APP_TYPE,
    CONF_AUTH_TYPE,
    CONF_COUNTRY_CODE,
    CONF_ENDPOINT,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    SMARTLIFE_APP,
    TUYA_COUNTRIES,
    TUYA_SMART_APP,
)
from homeassistant.core import HomeAssistant

MOCK_SMART_HOME_PROJECT_TYPE = 0
MOCK_INDUSTRY_PROJECT_TYPE = 1

MOCK_COUNTRY = "India"
MOCK_ACCESS_ID = "myAccessId"
MOCK_ACCESS_SECRET = "myAccessSecret"
MOCK_USERNAME = "myUsername"
MOCK_PASSWORD = "myPassword"
MOCK_ENDPOINT = TuyaCloudOpenAPIEndpoint.INDIA

TUYA_INPUT_DATA = {
    CONF_COUNTRY_CODE: MOCK_COUNTRY,
    CONF_ACCESS_ID: MOCK_ACCESS_ID,
    CONF_ACCESS_SECRET: MOCK_ACCESS_SECRET,
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
}

RESPONSE_SUCCESS = {
    "success": True,
    "code": 1024,
    "result": {"platform_url": MOCK_ENDPOINT},
}
RESPONSE_ERROR = {"success": False, "code": 123, "msg": "Error"}


@pytest.fixture(name="tuya")
def tuya_fixture() -> MagicMock:
    """Patch libraries."""
    with patch("homeassistant.components.tuya.config_flow.TuyaOpenAPI") as tuya:
        yield tuya


@pytest.fixture(name="tuya_setup", autouse=True)
def tuya_setup_fixture() -> None:
    """Mock tuya entry setup."""
    with patch("homeassistant.components.tuya.async_setup_entry", return_value=True):
        yield


@pytest.mark.parametrize(
    "app_type,side_effects, project_type",
    [
        ("", [RESPONSE_SUCCESS], 1),
        (TUYA_SMART_APP, [RESPONSE_ERROR, RESPONSE_SUCCESS], 0),
        (SMARTLIFE_APP, [RESPONSE_ERROR, RESPONSE_ERROR, RESPONSE_SUCCESS], 0),
    ],
)
async def test_user_flow(
    hass: HomeAssistant,
    tuya: MagicMock,
    app_type: str,
    side_effects: list[dict[str, Any]],
    project_type: int,
):
    """Test user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    tuya().connect = MagicMock(side_effect=side_effects)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TUYA_INPUT_DATA
    )
    await hass.async_block_till_done()

    country = [country for country in TUYA_COUNTRIES if country.name == MOCK_COUNTRY][0]

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USERNAME
    assert result["data"][CONF_ACCESS_ID] == MOCK_ACCESS_ID
    assert result["data"][CONF_ACCESS_SECRET] == MOCK_ACCESS_SECRET
    assert result["data"][CONF_USERNAME] == MOCK_USERNAME
    assert result["data"][CONF_PASSWORD] == MOCK_PASSWORD
    assert result["data"][CONF_ENDPOINT] == country.endpoint
    assert result["data"][CONF_APP_TYPE] == app_type
    assert result["data"][CONF_AUTH_TYPE] == project_type
    assert result["data"][CONF_COUNTRY_CODE] == country.country_code
    assert not result["result"].unique_id


async def test_error_on_invalid_credentials(hass, tuya):
    """Test when we have invalid credentials."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    tuya().connect = MagicMock(return_value=RESPONSE_ERROR)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=TUYA_INPUT_DATA
    )
    await hass.async_block_till_done()

    assert result["errors"]["base"] == "login_error"
    assert result["description_placeholders"]["code"] == RESPONSE_ERROR["code"]
    assert result["description_placeholders"]["msg"] == RESPONSE_ERROR["msg"]
