"""Test Flow-it integration setup and unload."""

from unittest.mock import AsyncMock

from flow_it_api.exceptions import FlowItAuthError, FlowItConnectionError
import pytest

from homeassistant.components.flow_it.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_unload_entry(hass: HomeAssistant, mock_flow_it: AsyncMock) -> None:
    """Test setting up and unloading the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flow-it Device",
        unique_id="00:11:22:33:44:55",
        data={
            "host": "http://1.1.1.1",
            "username": "api",
            "password": "test-password",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED
    mock_flow_it.return_value.refresh_state.assert_awaited()
    mock_flow_it.return_value.register_websocket_callback.assert_called_once()
    mock_flow_it.return_value.websocket.start.assert_called_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
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
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles exceptions correctly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flow-it Device",
        unique_id="00:11:22:33:44:55",
        data={
            "host": "http://1.1.1.1",
            "username": "api",
            "password": "test-password",
        },
    )
    entry.add_to_hass(hass)

    mock_flow_it.return_value.refresh_state.side_effect = exception
    mock_flow_it.return_value.get_info.side_effect = exception

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == expected_state
