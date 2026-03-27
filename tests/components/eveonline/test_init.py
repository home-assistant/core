"""Test the Eve Online integration setup."""

from unittest.mock import AsyncMock

import aiohttp
from eveonline import EveOnlineError
from eveonline.exceptions import EveOnlineAuthenticationError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import mock_server_status

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test successful setup of a config entry."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test setup failure when the API returns an error."""
    mock_eveonline_client.async_get_server_status.side_effect = EveOnlineError(
        "API unavailable"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test setup failure when authentication fails."""
    mock_eveonline_client.async_get_server_status.side_effect = (
        EveOnlineAuthenticationError("Token expired")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_network_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test setup failure when a network error occurs."""
    mock_eveonline_client.async_get_server_status.side_effect = aiohttp.ClientError(
        "Connection reset"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test successful unloading of a config entry."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_coordinator_optional_endpoint_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that errors on optional endpoints don't fail the coordinator.

    When an optional endpoint raises EveOnlineError, the coordinator
    should still load successfully with None/empty values for that data.
    """
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_wallet_balance.side_effect = EveOnlineError(
        "Endpoint down"
    )
    mock_eveonline_client.async_get_character_online.side_effect = EveOnlineError(
        "Endpoint down"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Optional endpoints should return None, sensor should be unavailable
    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_optional_endpoint_network_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that aiohttp.ClientError on optional endpoints degrades gracefully."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_wallet_balance.side_effect = aiohttp.ClientError(
        "Connection lost"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.test_capsuleer_wallet_balance")
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_auth_error_on_optional_endpoint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that auth errors on optional endpoints are not silently swallowed.

    Unlike generic EveOnlineError, EveOnlineAuthenticationError is re-raised
    from _fetch_optional so it propagates upward instead of returning None.
    During first refresh this causes the entry to fail setup (SETUP_RETRY).
    """
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_wallet_balance.side_effect = (
        EveOnlineAuthenticationError("Token revoked")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Auth errors propagate — entry should not be loaded
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_list_endpoint_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_eveonline_client: AsyncMock,
    setup_credentials: None,
) -> None:
    """Test that errors on list endpoints return empty lists gracefully."""
    mock_eveonline_client.async_get_server_status.return_value = mock_server_status()
    mock_eveonline_client.async_get_skill_queue.side_effect = EveOnlineError(
        "Service unavailable"
    )
    mock_eveonline_client.async_get_industry_jobs.side_effect = EveOnlineError(
        "Service unavailable"
    )
    mock_eveonline_client.async_get_market_orders.side_effect = EveOnlineError(
        "Service unavailable"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # List endpoints return empty lists, count sensors should show 0
    state = hass.states.get("sensor.test_capsuleer_skill_queue")
    assert state is not None
    assert state.state == "0"

    # Industry jobs and market orders should also show 0
    state = hass.states.get("sensor.test_capsuleer_industry_jobs")
    assert state is not None
    assert state.state == "0"
