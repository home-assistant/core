"""Test Flow-it integration setup and unload."""

from datetime import timedelta
from unittest.mock import AsyncMock

from flow_it_api.exceptions import FlowItAuthError, FlowItConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_unload_entry(
    hass: HomeAssistant, mock_flow_it: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading the integration."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_flow_it.return_value.refresh_state.assert_awaited()
    mock_flow_it.return_value.register_websocket_callback.assert_called_once()
    mock_flow_it.return_value.websocket.start.assert_called_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_flow_it.return_value.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (FlowItAuthError(), ConfigEntryState.SETUP_ERROR),
        (FlowItConnectionError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_exceptions(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles exceptions correctly."""
    mock_flow_it.return_value.refresh_state.side_effect = exception
    mock_flow_it.return_value.get_info.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == expected_state


async def test_setup_auth_failed_starts_reauth(
    hass: HomeAssistant, mock_flow_it: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test an authentication error during setup starts a reauth flow."""
    mock_flow_it.return_value.refresh_state.side_effect = FlowItAuthError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_update_auth_failed_starts_reauth(
    hass: HomeAssistant,
    mock_flow_it: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an authentication error during a scheduled refresh starts reauth."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_flow_it.return_value.refresh_state.side_effect = FlowItAuthError
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
