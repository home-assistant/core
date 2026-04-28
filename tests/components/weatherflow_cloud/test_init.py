"""Tests for weatherflow_cloud __init__ setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from weatherflow4py.ws import WeatherFlowWebsocketAPI

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_websocket_api_instance():
    """Mock WeatherFlowWebsocketAPI instance to track connect() calls."""
    mock_ws_instance = AsyncMock(spec=WeatherFlowWebsocketAPI)
    mock_ws_instance.connect = AsyncMock()
    mock_ws_instance.send_message = AsyncMock()
    mock_ws_instance.register_callback = MagicMock()
    mock_ws_instance.stop_all_listeners = AsyncMock()
    mock_ws_instance.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.weatherflow_cloud.WeatherFlowWebsocketAPI",
            return_value=mock_ws_instance,
        ),
        patch(
            "homeassistant.components.weatherflow_cloud.coordinator.WeatherFlowWebsocketAPI",
            return_value=mock_ws_instance,
        ),
    ):
        yield mock_ws_instance


async def test_websocket_connect_called_once(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
    mock_websocket_api_instance: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the shared websocket is connected exactly once during setup."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_websocket_api_instance.connect.call_count == 1


async def test_entry_unload(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
    mock_websocket_api_instance: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unloading an entry closes the websocket."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_websocket_api_instance.close.assert_called_once()


async def test_setup_failure_cleans_up_websocket(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
    mock_websocket_api_instance: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test partial setup failure stops listeners and closes the websocket."""
    mock_config_entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("setup failed"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED
    mock_websocket_api_instance.stop_all_listeners.assert_awaited_once()
    mock_websocket_api_instance.close.assert_awaited_once()
