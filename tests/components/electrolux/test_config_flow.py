"""Unit test for Electrolux config flow."""

from unittest.mock import AsyncMock, patch

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


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test a successful user config flow."""
    with (
        patch(
            "homeassistant.components.electrolux.config_flow.TokenManager"
        ) as mock_token_manager,
        patch(
            "homeassistant.components.electrolux.config_flow.ApplianceClient"
        ) as mock_appliance_client,
    ):
        mock_token_manager_instance = mock_token_manager.return_value
        mock_token_manager_instance.get_user_id.return_value = "userId"

        mock_appliance_client_instance = AsyncMock()
        mock_appliance_client_instance.test_connection.return_value = None
        mock_appliance_client.return_value = mock_appliance_client_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result.get("type") == "form"
        assert result.get("errors") == {}

        user_input = {
            CONF_ACCESS_TOKEN: "test_access_token",
            CONF_REFRESH_TOKEN: "test_refresh_token",
            CONF_API_KEY: "test_api_key",
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

        assert result2.get("type") == "create_entry"
        assert result2.get("title") == "Electrolux"
        assert result2.get("data") == user_input


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == "form"

    with patch(
        "homeassistant.components.electrolux.config_flow.TokenManager"
    ) as mock_token_manager:
        mock_token_manager_instance = mock_token_manager.return_value
        mock_token_manager_instance.ensure_credentials.side_effect = (
            InvalidCredentialsException()
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "api_key": "api_key",
                "refresh_token": "invalid_token",
                "access_token": "invalid_token",
            },
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"base": "auth_failed"}


async def test_user_flow_failed_connection(hass: HomeAssistant) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == "form"

    with patch(
        "homeassistant.components.electrolux.config_flow.ApplianceClient"
    ) as mock_appliance_client:
        mock_appliance_client_instance = AsyncMock()
        mock_appliance_client_instance = mock_appliance_client.return_value
        mock_appliance_client_instance.test_connection.side_effect = (
            FailedConnectionException()
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "api_key": "api_key",
                "refresh_token": "invalid_token",
                "access_token": "invalid_token",
            },
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == "form"

    with patch(
        "homeassistant.components.electrolux.config_flow.ApplianceClient"
    ) as mock_appliance_client:
        mock_appliance_client_instance = AsyncMock()
        mock_appliance_client_instance = mock_appliance_client.return_value
        mock_appliance_client_instance.test_connection.side_effect = Exception()

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "api_key": "api_key",
                "refresh_token": "invalid_token",
                "access_token": "invalid_token",
            },
        )

    assert result2.get("type") == data_entry_flow.FlowResultType.FORM
    assert result2.get("errors") == {"base": "unknown"}


async def test_user_flow_abort_flow(hass: HomeAssistant) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result.get("type") == "form"

    # Patch _authenticate_user to raise AbortFlow
    with patch(
        "homeassistant.components.electrolux.config_flow.ElectroluxConfigFlow._authenticate_user",
        side_effect=data_entry_flow.AbortFlow("already_in_progress"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "api_key": "some_api_key",
                "refresh_token": "some_refresh_token",
                "access_token": "some_access_token",
            },
        )

    assert result2.get("type") == "abort"
    assert result2.get("reason") == "already_in_progress"
