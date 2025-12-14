"""Test the Overseerr coordinator."""

from unittest.mock import AsyncMock

import pytest
from python_overseerr import OverseerrAuthenticationError, OverseerrConnectionError

from homeassistant.components.overseerr.coordinator import OverseerrCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_fetch_data_success(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator successfully fetches both request and issue data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator: OverseerrCoordinator = mock_config_entry.runtime_data

    # Verify coordinator has data from both API calls
    assert coordinator.data is not None
    assert coordinator.data.requests is not None
    assert coordinator.data.issues is not None

    # Verify request data
    assert coordinator.data.requests.total == 50
    assert coordinator.data.requests.movie == 30
    assert coordinator.data.requests.tv == 20
    assert coordinator.data.requests.pending == 10
    assert coordinator.data.requests.declined == 5
    assert coordinator.data.requests.processing == 15
    assert coordinator.data.requests.available == 20

    # Verify issue data
    assert coordinator.data.issues.total == 15
    assert coordinator.data.issues.video == 6
    assert coordinator.data.issues.audio == 4
    assert coordinator.data.issues.subtitles == 3
    assert coordinator.data.issues.others == 2
    assert coordinator.data.issues.open == 10
    assert coordinator.data.issues.closed == 5

    # Verify both API methods were called
    mock_overseerr_client.get_request_count.assert_called()
    mock_overseerr_client.get_issue_count.assert_called()


async def test_coordinator_auth_error_on_request_count(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles authentication error when fetching request count."""
    mock_overseerr_client.get_request_count.side_effect = OverseerrAuthenticationError(
        "Invalid API key"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_auth_error_on_issue_count(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles authentication error when fetching issue count."""
    mock_overseerr_client.get_issue_count.side_effect = OverseerrAuthenticationError(
        "Invalid API key"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_connection_error_on_request_count(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles connection error when fetching request count."""
    mock_overseerr_client.get_request_count.side_effect = OverseerrConnectionError(
        "Connection failed"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_connection_error_on_issue_count(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles connection error when fetching issue count."""
    mock_overseerr_client.get_issue_count.side_effect = OverseerrConnectionError(
        "Connection failed"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_data(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator refresh updates data."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: OverseerrCoordinator = mock_config_entry.runtime_data

    # Record initial call counts
    initial_request_calls = mock_overseerr_client.get_request_count.call_count
    initial_issue_calls = mock_overseerr_client.get_issue_count.call_count

    # Trigger a refresh
    await coordinator.async_refresh()

    # Verify both API methods were called again
    assert (
        mock_overseerr_client.get_request_count.call_count == initial_request_calls + 1
    )
    assert mock_overseerr_client.get_issue_count.call_count == initial_issue_calls + 1

    # Data should still be valid
    assert coordinator.data.requests.total == 50
    assert coordinator.data.issues.total == 15


async def test_coordinator_auth_error_raises_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator raises ConfigEntryAuthFailed on authentication error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: OverseerrCoordinator = mock_config_entry.runtime_data

    # Simulate auth error on next update
    mock_overseerr_client.get_request_count.side_effect = OverseerrAuthenticationError(
        "Invalid API key"
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_connection_error_raises_update_failed(
    hass: HomeAssistant,
    mock_overseerr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator raises UpdateFailed on connection error."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator: OverseerrCoordinator = mock_config_entry.runtime_data

    # Simulate connection error on next update
    mock_overseerr_client.get_request_count.side_effect = OverseerrConnectionError(
        "Timeout"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
