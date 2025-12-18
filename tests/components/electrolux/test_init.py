"""Unit test for Electrolux init flow."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.electrolux import ElectroluxData
from homeassistant.components.electrolux.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry():
    """Create a mock Electrolux config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="mock_unique_id",
        data={
            CONF_API_KEY: "test-api-key",
            CONF_ACCESS_TOKEN: "test-access-token",
            CONF_REFRESH_TOKEN: "test-refresh-token",
        },
    )


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of the Electrolux integration."""

    with (
        patch(
            "electrolux_group_developer_sdk.auth.token_manager.TokenManager.__init__",
            return_value=None,
        ),
        patch(
            "electrolux_group_developer_sdk.auth.token_manager.TokenManager.ensure_credentials"
        ) as mock_ensure_credentials,
        patch(
            "electrolux_group_developer_sdk.auth.token_manager.TokenManager.get_user_id"
        ) as mock_get_user_id,
        patch(
            "electrolux_group_developer_sdk.client.appliance_client.ApplianceClient.test_connection"
        ) as mock_appliance_client_test_connection,
        patch(
            "electrolux_group_developer_sdk.client.appliance_client.ApplianceClient.start_event_stream"
        ) as mock_appliance_client_start_event_stream,
        patch(
            "homeassistant.components.electrolux.api.ElectroluxApiClient"
        ) as mock_api_client_class,
        patch(
            "homeassistant.components.electrolux.coordinator.ElectroluxDataUpdateCoordinator"
        ) as mock_coordinator_class,
    ):
        # Setup TokenManager behavior
        mock_ensure_credentials.return_value = None
        mock_get_user_id.return_value = "userId"

        # Setup ApplianceClient mock
        mock_appliance_client_test_connection.return_value = None
        mock_appliance_client_start_event_stream.return_value = None

        # Mock ElectroluxApiClient and its appliance list
        mock_appliance = AsyncMock()
        mock_appliance.appliance.applianceId = "test_appliance_id"
        mock_api_client = AsyncMock()
        mock_api_client.fetch_appliance_data.return_value = [mock_appliance]
        mock_api_client.add_listener.return_value = None
        mock_api_client_class.return_value = mock_api_client

        # Setup coordinator
        mock_coordinator = AsyncMock()
        mock_coordinator.async_config_entry_first_refresh.return_value = None
        mock_coordinator.last_update_success = True
        mock_coordinator_class.return_value = mock_coordinator

        mock_config_entry.runtime_data = ElectroluxData(
            client=mock_api_client,
            coordinators={},
            sse_task=Mock(),
        )

        # Add and setup config entry
        mock_config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check integration is loaded
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_config_entry.runtime_data is not None
        assert isinstance(mock_config_entry.runtime_data, ElectroluxData)

        # Unload the config entry
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
