"""Tests for the UpCloud config flow."""
from unittest.mock import patch

import requests.exceptions
import requests_mock
from requests_mock import ANY
from upcloud_api import UpCloudAPIError

from homeassistant import config_entries
from homeassistant.components.upcloud.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}

FIXTURE_USER_INPUT_OPTIONS = {
    CONF_SCAN_INTERVAL: "120",
}


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test we show user form on connection error."""
    requests_mock.request(ANY, ANY, exc=requests.exceptions.ConnectionError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_login_error(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
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

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_success(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test successful flow provides entry creation data."""
    requests_mock.request(ANY, "/1.3/account", text='{"account":{"username":"user"}}')
    requests_mock.request(ANY, "/1.3/server", text='{"servers": {"server":[]}}')
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]


async def test_options(hass: HomeAssistant) -> None:
    """Test options produce expected data."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, options=FIXTURE_USER_INPUT_OPTIONS
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.upcloud.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=FIXTURE_USER_INPUT_OPTIONS,
    )
    assert result["data"][CONF_SCAN_INTERVAL] == int(
        FIXTURE_USER_INPUT_OPTIONS[CONF_SCAN_INTERVAL]
    )


async def test_already_configured(hass: HomeAssistant, requests_mock) -> None:
    """Test duplicate entry aborts and updates data."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_USER_INPUT[CONF_USERNAME],
        data=FIXTURE_USER_INPUT,
        options=FIXTURE_USER_INPUT_OPTIONS,
    )
    config_entry.add_to_hass(hass)

    new_user_input = FIXTURE_USER_INPUT.copy()
    new_user_input[CONF_PASSWORD] += "_changed"

    requests_mock.request(ANY, "/1.3/account", text='{"account":{"username":"user"}}')
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=new_user_input
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_USERNAME] == new_user_input[CONF_USERNAME]
    assert config_entry.data[CONF_PASSWORD] == new_user_input[CONF_PASSWORD]
