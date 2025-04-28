"""Test the Roth Touchline SL config flow."""

from unittest.mock import AsyncMock

import pytest
from pytouchlinesl.client import RothAPIError

from homeassistant.components.touchline_sl.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

RESULT_UNIQUE_ID = "12345"

CONFIG_DATA = {
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def test_config_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_touchlinesl_client: AsyncMock
) -> None:
    """Test the happy path where the provided username/password result in a new entry."""
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
    """Test for invalid credentials or API connection errors, and that the form can recover."""
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


async def test_config_flow_failure_adding_non_unique_account(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
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
