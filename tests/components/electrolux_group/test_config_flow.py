"""Unit test for Electrolux config flow."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from electrolux_group_developer_sdk.auth.invalid_credentials_exception import (
    InvalidCredentialsException,
)
from electrolux_group_developer_sdk.client.failed_connection_exception import (
    FailedConnectionException,
)

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.electrolux_group import ElectroluxData
from homeassistant.components.electrolux_group.const import (
    CONF_REFRESH_TOKEN,
    DOMAIN,
    NEW_APPLIANCE,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant) -> None:
    """Test a successful user config flow."""
    with (
        patch(
            "homeassistant.components.electrolux_group.config_flow.TokenManager"
        ) as mock_token_manager,
        patch(
            "homeassistant.components.electrolux_group.config_flow.ApplianceClient"
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

        assert result["type"] == "form"
        assert result["errors"] == {}

        user_input = {
            CONF_ACCESS_TOKEN: "test_access_token",
            CONF_REFRESH_TOKEN: "test_refresh_token",
            CONF_API_KEY: "test_api_key",
        }

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=user_input
        )

        assert result2["type"] == "create_entry"
        assert result2["title"] == "Electrolux"
        assert result2["data"] == user_input


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    with patch(
        "homeassistant.components.electrolux_group.config_flow.TokenManager"
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

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "auth_failed"}


async def test_user_flow_failed_connection(hass: HomeAssistant) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    with patch(
        "homeassistant.components.electrolux_group.config_flow.ApplianceClient"
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

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_flow_unknown_error(hass: HomeAssistant) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    with patch(
        "homeassistant.components.electrolux_group.config_flow.ApplianceClient"
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

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_user_flow_abort_flow(hass: HomeAssistant) -> None:
    """Test an invalid auth config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"

    # Patch _authenticate_user to raise AbortFlow
    with patch(
        "homeassistant.components.electrolux_group.config_flow.ElectroluxConfigFlow._authenticate_user",
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

    assert result2["type"] == "abort"
    assert result2["reason"] == "already_in_progress"


async def test_discovery_flow_success(hass: HomeAssistant) -> None:
    """Test a successful Electrolux discovery and confirmation flow."""
    mock_appliance = MagicMock()
    mock_appliance.appliance.applianceId = "123"
    mock_appliance.appliance.applianceName = "Washer"
    mock_appliance.details.applianceInfo.brand = "Electrolux"

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Electrolux",
        data={
            CONF_ACCESS_TOKEN: "access_token",
            CONF_REFRESH_TOKEN: "refresh_token",
            CONF_API_KEY: "api_key",
        },
        unique_id="userId",
    )
    mock_entry.runtime_data = ElectroluxData(
        client=Mock(),
        coordinators={},
        sse_task=Mock(),
    )
    mock_entry.add_to_hass(hass)

    discovery_appliance_data = {
        "discovery_appliance_data": mock_appliance,
        "entry": mock_entry,
    }

    with (
        patch(
            "homeassistant.components.electrolux_group.config_flow.ElectroluxDataUpdateCoordinator"
        ) as mock_coordinator,
        patch(
            "homeassistant.components.electrolux_group.config_flow.async_dispatcher_send"
        ) as mock_dispatch,
        patch(
            "homeassistant.components.electrolux_group.config_flow.persistent_notification.async_create"
        ) as mock_notification,
    ):
        mock_coordinator_instance = AsyncMock()
        mock_coordinator.return_value = mock_coordinator_instance

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "electrolux_discovery"},
            data=discovery_appliance_data,
        )

        # Flow should show confirmation form
        assert result["type"] == "form"
        assert result["step_id"] == "discovery_confirm"
        assert "device" in result["description_placeholders"]

        # Simulate user confirming the discovered appliance
        hass.data[mock_entry.entry_id] = MagicMock(client=AsyncMock(), coordinators={})

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

        # Flow should abort after adding appliance
        assert result2["type"] == "abort"
        assert result2["reason"] == "added_to_existing_entry"

        # Ensure coordinator was created, refreshed, and listener added
        mock_coordinator.assert_called_once()
        mock_coordinator_instance.async_refresh.assert_awaited_once()
        mock_dispatch.assert_called_once_with(
            hass, NEW_APPLIANCE, mock_entry.entry_id, mock_appliance
        )
        mock_notification.assert_called_once()


async def test_discovery_flow_missing_id(hass: HomeAssistant) -> None:
    """Test discovery flow aborts when appliance has no ID."""
    flow = hass.config_entries.flow

    discovery_appliance_data = {
        "discovery_appliance_data": MagicMock(appliance=MagicMock(applianceId=None))
    }

    result = await flow.async_init(
        DOMAIN,
        context={"source": "electrolux_discovery"},
        data=discovery_appliance_data,
    )

    # Expected: abort since applianceId is None
    assert result["type"] == "abort"
    assert result["reason"] == "missing_id"
