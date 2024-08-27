"""Test the Roth Touchline SL config flow."""

from unittest.mock import AsyncMock

import pytest
from pytouchlinesl.client import RothAPIError

from homeassistant.components.touchline_sl.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_touchlinesl_client: AsyncMock
) -> None:
    """Test the happy path where the provided username/password result in a new entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {"password": "test-password", "username": "test-username"}
    assert result["result"].unique_id == "12345"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("status_code", "error_base"), [(401, "invalid_auth"), (502, "cannot_connect")]
)
async def test_config_flow_failure_api_exceptions(
    hass: HomeAssistant,
    status_code: int,
    error_base: str,
    mock_setup_entry: AsyncMock,
    mock_touchlinesl_client: AsyncMock,
) -> None:
    """Test for invalid credentials or API connection errors, and that the form can recover."""
    mock_touchlinesl_client.user_id.side_effect = RothAPIError(status=status_code)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # "Fix" the problem, and try again.
    mock_touchlinesl_client.user_id.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {"password": "test-password", "username": "test-username"}
    assert result["result"].unique_id == "12345"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_flow_failure_adding_non_unique_account(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_touchlinesl_client: AsyncMock,
) -> None:
    """Test that the config flow fails when user tries to add duplicate accounts."""
    # Add the first account
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-username"
    assert result["data"] == {"password": "test-password", "username": "test-username"}
    assert result["result"].unique_id == "12345"
    assert len(mock_setup_entry.mock_calls) == 1

    # Try re-adding the account
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert len(mock_setup_entry.mock_calls) == 1
