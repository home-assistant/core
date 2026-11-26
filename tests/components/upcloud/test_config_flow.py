"""Tests for the UpCloud config flow."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests.exceptions
import requests_mock
from requests_mock import ANY
from upcloud_api import UpCloudAPIError

from homeassistant import config_entries
from homeassistant.components.upcloud.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
}


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_connection_error(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test we show user form on connection error."""
    requests_mock.request(ANY, ANY, exc=requests.exceptions.ConnectionError())

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    requests_mock.request(ANY, "/1.3/account", text='{"account":{"username":"user"}}')
    requests_mock.request(ANY, "/1.3/server", text='{"servers": {"server":[]}}')
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_login_error(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test we show user form with appropriate error on response failure."""
    requests_mock.request(
        ANY,
        ANY,
        exc=UpCloudAPIError(
            error_code="AUTHENTICATION_FAILED",
            error_message="Authentication failed using the given"
            " username and password.",
        ),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    requests_mock.request(ANY, "/1.3/account", text='{"account":{"username":"user"}}')
    requests_mock.request(ANY, "/1.3/server", text='{"servers": {"server":[]}}')
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_success(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test successful flow provides entry creation data."""
    requests_mock.request(ANY, "/1.3/account", text='{"account":{"username":"user"}}')
    requests_mock.request(ANY, "/1.3/server", text='{"servers": {"server":[]}}')

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=FIXTURE_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
    assert result["result"].unique_id == FIXTURE_USER_INPUT[CONF_USERNAME]


async def test_already_configured(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test duplicate entry aborts and updates data."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_USER_INPUT[CONF_USERNAME],
        data=FIXTURE_USER_INPUT,
    )
    config_entry.add_to_hass(hass)

    new_user_input = FIXTURE_USER_INPUT.copy()
    new_user_input[CONF_PASSWORD] += "_changed"

    requests_mock.request(ANY, "/1.3/account", text='{"account":{"username":"user"}}')

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=new_user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_USERNAME] == new_user_input[CONF_USERNAME]
    assert config_entry.data[CONF_PASSWORD] == new_user_input[CONF_PASSWORD]


async def test_reauth(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test reauthentication updates the password and reloads the entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_USER_INPUT[CONF_USERNAME],
        data=FIXTURE_USER_INPUT,
    )
    config_entry.add_to_hass(hass)
    requests_mock.request(ANY, "/1.3/account", text='{"account":{"username":"user"}}')
    requests_mock.request(ANY, "/1.3/server", text='{"servers": {"server":[]}}')

    result = await config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "new_pass"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data == {CONF_USERNAME: "user", CONF_PASSWORD: "new_pass"}
    assert config_entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        pytest.param(
            UpCloudAPIError(
                error_code="AUTHENTICATION_FAILED",
                error_message="Authentication failed using the given"
                " username and password.",
            ),
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            requests.exceptions.ConnectionError(), "cannot_connect", id="cannot_connect"
        ),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    exc: Exception,
    error: str,
) -> None:
    """Test reauthentication errors and a successful retry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_USER_INPUT[CONF_USERNAME],
        data=FIXTURE_USER_INPUT,
    )
    config_entry.add_to_hass(hass)
    requests_mock.request(ANY, ANY, exc=exc)

    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "new_pass"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    requests_mock.request(ANY, "/1.3/account", text='{"account":{"username":"user"}}')
    requests_mock.request(ANY, "/1.3/server", text='{"servers": {"server":[]}}')
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "new_pass"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_PASSWORD] == "new_pass"
