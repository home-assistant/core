"""Unit test for Electrolux config flow."""

from unittest.mock import AsyncMock

from electrolux_group_developer_sdk.auth.invalid_credentials_exception import (
    InvalidCredentialsException,
)
from electrolux_group_developer_sdk.client.bad_credentials_exception import (
    BadCredentialsException,
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

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Electrolux for mock@email.com"
    assert result["data"] == valid_user_input
    assert result["result"].unique_id == "mock_user_id"


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, appliances: AsyncMock, mock_token_manager: AsyncMock
) -> None:
    """Test an invalid auth config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM

    mock_token_manager.ensure_credentials.side_effect = InvalidCredentialsException

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_user_input,
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_token_manager.ensure_credentials.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Electrolux for mock@email.com"
    assert result["data"] == valid_user_input
    assert result["result"].unique_id == "mock_user_id"


async def test_user_flow_bad_credentials(
    hass: HomeAssistant, appliances: AsyncMock, mock_token_manager: AsyncMock
) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM

    appliances.test_connection.side_effect = BadCredentialsException()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_user_input,
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    appliances.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Electrolux for mock@email.com"
    assert result["data"] == valid_user_input
    assert result["result"].unique_id == "mock_user_id"


async def test_user_flow_failed_connection(
    hass: HomeAssistant, appliances: AsyncMock, mock_token_manager: AsyncMock
) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM

    appliances.test_connection.side_effect = FailedConnectionException()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=invalid_user_input,
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    appliances.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Electrolux for mock@email.com"
    assert result["data"] == valid_user_input
    assert result["result"].unique_id == "mock_user_id"


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

    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=valid_user_input,
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_successful(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reauth step succeeds and updates the config entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # mock_appliance_client.test_connection.return_value = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data == valid_user_input


async def test_reauth_invalid_auth(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with invalid authentication."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_token_manager.ensure_credentials.side_effect = InvalidCredentialsException

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=invalid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_token_manager.ensure_credentials.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data == valid_user_input


async def test_reauth_bad_credentials(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with bad credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_token_manager.ensure_credentials.side_effect = BadCredentialsException

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=invalid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_token_manager.ensure_credentials.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data == valid_user_input


async def test_reauth_failed_connection(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow failed connection."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_appliance_client.test_connection.side_effect = FailedConnectionException

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=invalid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_appliance_client.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert mock_config_entry.data == valid_user_input


async def test_reauth_mismatched_entry(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow mismatched user id error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_token_manager.get_user_id.return_value = "different_user_id"
    mock_appliance_client.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "wrong_account"


async def test_reconfigure_successful(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure step succeeds and updates the config entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # mock_appliance_client.test_connection.return_value = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert mock_config_entry.data == valid_user_input


async def test_reconfigure_invalid_auth(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow with invalid authentication."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_token_manager.ensure_credentials.side_effect = InvalidCredentialsException

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=invalid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_token_manager.ensure_credentials.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert mock_config_entry.data == valid_user_input


async def test_reconfigure_bad_credentials(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow with bad credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_token_manager.ensure_credentials.side_effect = BadCredentialsException

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=invalid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_token_manager.ensure_credentials.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert mock_config_entry.data == valid_user_input


async def test_reconfigure_failed_connection(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow failed connection."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_appliance_client.test_connection.side_effect = FailedConnectionException

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=invalid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_appliance_client.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert mock_config_entry.data == valid_user_input


async def test_reconfigure_mismatched_entry(
    hass: HomeAssistant,
    mock_appliance_client: AsyncMock,
    mock_token_manager: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow mismatched user id error."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_token_manager.get_user_id.return_value = "different_user_id"
    mock_appliance_client.test_connection.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=valid_user_input
    )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
