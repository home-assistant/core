"""Tests for Poolside setup and unload."""

from homeassistant.components.poolside.client import (
    PoolsideAuthError,
    PoolsideConnectionError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FakePoolsideClient

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A successful connect populates runtime_data and forwards platforms."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_poolside_client
    mock_poolside_client.async_connect.assert_awaited_once()
    mock_poolside_client.async_get_control_layout.assert_awaited_once()


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A connection failure raises ConfigEntryNotReady, leaving the entry retryable."""
    mock_poolside_client.async_connect.side_effect = PoolsideConnectionError("nope")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """A revoked/unpaired client triggers the reauth flow."""
    mock_poolside_client.async_connect.side_effect = PoolsideAuthError("revoked")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(mock_config_entry.domain)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_poolside_client: FakePoolsideClient,
) -> None:
    """Unloading the entry disconnects the client."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_poolside_client.async_disconnect.assert_awaited_once()
