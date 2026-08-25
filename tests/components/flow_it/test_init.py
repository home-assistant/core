"""Test Flow-it integration setup and unload."""

from unittest.mock import AsyncMock

from flow_it_api.exceptions import FlowItAuthError, FlowItConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
