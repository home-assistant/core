"""Test the Roth Touchline SL config flow."""

from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytouchlinesl.client import RothAPIError

from homeassistant.components.touchline_sl.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

RESULT_UNIQUE_ID = "12345"

CONFIG_DATA = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def test_config_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_touchlinesl_client: AsyncMock
) -> None:
    """Test the happy path where username/password result in a new entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == CONFIG_DATA
    assert result["result"].unique_id == RESULT_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        (RothAPIError(status=401), "invalid_auth"),
        (RothAPIError(status=502), "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_config_flow_failure_api_exceptions(
    hass: HomeAssistant,
    exception: Exception,
    error_base: str,
    mock_setup_entry: AsyncMock,
    mock_touchlinesl_client: AsyncMock,
) -> None:
    """Test for invalid credentials or API errors, and form recovery."""
    mock_touchlinesl_client.user_id.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # "Fix" the problem, and try again.
    mock_touchlinesl_client.user_id.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == CONFIG_DATA
    assert result["result"].unique_id == RESULT_UNIQUE_ID
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_config_flow_failure_adding_non_unique_account(
    hass: HomeAssistant,
    mock_touchlinesl_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the config flow fails when user tries to add duplicate accounts."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], CONFIG_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry", "mock_touchlinesl_client")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauthentication flow updates the password."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"][CONF_USERNAME] == "test-username"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "new-password",
    }


@pytest.mark.parametrize(
    ("exception", "error_base"),
    [
        pytest.param(RothAPIError(status=401), "invalid_auth", id="invalid_auth"),
        pytest.param(RothAPIError(status=502), "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: AsyncMock,
    exception: Exception,
    error_base: str,
) -> None:
    """Test reauthentication errors and recovery."""
    mock_config_entry.add_to_hass(hass)
    mock_touchlinesl_client.user_id.side_effect = exception

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error_base}

    mock_touchlinesl_client.user_id.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_touchlinesl_client: AsyncMock,
) -> None:
    """Test reauthentication aborts when the credentials belong to another account."""
    mock_config_entry.add_to_hass(hass)
    mock_touchlinesl_client.user_id.return_value = 67890

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == CONFIG_DATA
