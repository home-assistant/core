"""Tests for the SleepIQ config flow."""

import pytest
from requests_mock import ANY

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.sleepiq.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME

USER_INPUT = {
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_SCAN_INTERVAL: 60,
}


async def test_show_set_form(hass) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_login_error(hass, requests_mock) -> None:
    """Test we show user form with appropriate error on login failure."""
    requests_mock.request(ANY, ANY, exc=ValueError)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.parametrize(
    "requests_mock_fixture", [""], indirect=["requests_mock_fixture"]
)
async def test_success(hass, requests_mock_fixture) -> None:
    """Test successful flow provides entry creation data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == USER_INPUT[CONF_PASSWORD]
    assert result["data"][CONF_SCAN_INTERVAL] == USER_INPUT[CONF_SCAN_INTERVAL]
