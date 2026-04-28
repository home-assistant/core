"""Tests for weatherflow_cloud __init__ setup."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from weatherflow4py.ws import WeatherFlowWebsocketAPI

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_websocket_api_cls():
    """Mock the WeatherFlowWebsocketAPI class to track connect() calls."""
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


async def test_websocket_connect_called_once_not_twice(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
    mock_websocket_api_cls: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Regression test for issue #164441.

    Both websocket coordinators share a single WeatherFlowWebsocketAPI instance.
    connect() must be called exactly once during setup — not once per coordinator —
    to avoid ConnectionClosedOK errors when the second connect() races with the
    first coordinator's send_message() calls.
    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # connect() must be called exactly once, not once per coordinator
    assert mock_websocket_api_cls.connect.call_count == 1, (
        f"connect() was called {mock_websocket_api_cls.connect.call_count} times "
        "but should only be called once. Calling it twice on a shared websocket "
        "instance causes ConnectionClosedOK errors (issue #164441)."
    )


async def test_entry_unload(
    hass: HomeAssistant,
    mock_rest_api: AsyncMock,
    mock_websocket_api_cls: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unloading an entry cleans up the websocket."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_websocket_api_cls.close.assert_called_once()
