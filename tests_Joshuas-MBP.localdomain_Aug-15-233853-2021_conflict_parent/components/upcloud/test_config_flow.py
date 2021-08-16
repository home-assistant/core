"""Tests for the UpCloud config flow."""

import requests.exceptions
from requests_mock import ANY
from upcloud_api import UpCloudAPIError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.upcloud.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}

FIXTURE_USER_INPUT_OPTIONS = {
    CONF_SCAN_INTERVAL: "120",
}


async def test_show_set_form(hass):
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_connection_error(hass, requests_mock):
    """Test we show user form on connection error."""
    requests_mock.request(ANY, ANY, exc=requests.exceptions.ConnectionError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_login_error(hass, requests_mock):
    """Test we show user form with appropriate error on response failure."""
    requests_mock.request(
        ANY,
        ANY,
        exc=UpCloudAPIError(
            error_code="AUTHENTICATION_FAILED",
            error_message="Authentication failed using the given username and password.",
        ),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_success(hass, requests_mock):
    """Test successful flow provides entry creation data."""
    requests_mock.request(ANY, ANY, text='{"account":{"username":"user"}}')
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]


async def test_options(hass):
    """Test options produce expected data."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, options=FIXTURE_USER_INPUT_OPTIONS
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=FIXTURE_USER_INPUT_OPTIONS,
    )
    assert result["data"][CONF_SCAN_INTERVAL] == int(
        FIXTURE_USER_INPUT_OPTIONS[CONF_SCAN_INTERVAL]
    )
