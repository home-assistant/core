"""Unit test for Electrolux config flow."""

from unittest.mock import AsyncMock

from electrolux_group_developer_sdk.auth.invalid_credentials_exception import (
    InvalidCredentialsException,
)
from electrolux_group_developer_sdk.client.failed_connection_exception import (
    FailedConnectionException,
)

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.electrolux.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

valid_user_input = {
    CONF_API_KEY: "test_api_key",
    CONF_ACCESS_TOKEN: "test_access_token",
    CONF_REFRESH_TOKEN: "test_refresh_token",
}

invalid_user_input = {
    CONF_API_KEY: "api_key",
    CONF_ACCESS_TOKEN: "invalid_token",
    CONF_REFRESH_TOKEN: "invalid_token",
}


async def test_user_flow_success(
    hass: HomeAssistant, appliances: AsyncMock, mock_token_manager: AsyncMock
) -> None:
    """Test a successful user config flow."""
    mock_token_manager.get_user_id.return_value = "userId"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == "form"
    assert result.get("errors") == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result2.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "Electrolux"
    assert result2.get("data") == valid_user_input


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, appliances: AsyncMock, mock_token_manager: AsyncMock
) -> None:
    """Test an invalid auth config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == data_entry_flow.FlowResultType.FORM

    mock_token_manager.ensure_credentials.side_effect = InvalidCredentialsException

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_user_input,
    )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"base": "invalid_auth"}

    mock_token_manager.ensure_credentials.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input=valid_user_input
    )

    assert result3.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Electrolux"
    assert result3.get("data") == valid_user_input


async def test_user_flow_failed_connection(
    hass: HomeAssistant, appliances: AsyncMock, mock_token_manager: AsyncMock
) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == "form"

    appliances.test_connection.side_effect = FailedConnectionException()

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_user_input,
    )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"base": "cannot_connect"}

    appliances.test_connection.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], user_input=valid_user_input
    )

    assert result3.get("type") == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result3.get("title") == "Electrolux"
    assert result3.get("data") == valid_user_input


async def test_user_flow_duplicate_entry(
    hass: HomeAssistant,
    appliances: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an invalid auth config flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == data_entry_flow.FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=valid_user_input,
    )

    assert result2.get("type") == data_entry_flow.FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"
