"""Tests for the coordinator of the WLED integration."""
import asyncio
from unittest.mock import MagicMock

import pytest
from wled import WLEDConnectionClosed, WLEDConnectionError

from homeassistant.components.wled.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_not_supporting_websocket(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Ensure no WebSocket attempt is made if non-WebSocket device."""
    assert mock_wled.connect.call_count == 0


@pytest.mark.parametrize("mock_wled", ["wled/rgb_websocket.json"], indirect=True)
async def test_websocket_already_connected(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Ensure no a second WebSocket connection is made, if already connected."""
    assert mock_wled.connect.call_count == 1

    mock_wled.connected = True
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert mock_wled.connect.call_count == 1


@pytest.mark.parametrize("mock_wled", ["wled/rgb_websocket.json"], indirect=True)
async def test_websocket_connect_error_no_listen(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Ensure we don't start listening if WebSocket connection failed."""
    assert mock_wled.connect.call_count == 1
    assert mock_wled.listen.call_count == 1

    mock_wled.connect.side_effect = WLEDConnectionError
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert mock_wled.connect.call_count == 2
    assert mock_wled.listen.call_count == 1


@pytest.mark.parametrize("mock_wled", ["wled/rgb_websocket.json"], indirect=True)
async def test_websocket_disconnect(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test WebSocket connection."""
    state = hass.states.get("light.wled_websocket")
    assert state

    # There is no Future in place yet...
    assert mock_wled.connect.call_count == 1
    assert mock_wled.listen.call_count == 1
    assert mock_wled.disconnect.call_count == 1

    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback):
        connection_connected.set_result(callback)
        await connection_finished

    # Mock out wled.listen with a Future
    mock_wled.listen.side_effect = connect

    # Next refresh it should connect
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    callback = await connection_connected

    # Connected to WebSocket, disconnect not called
    assert mock_wled.connect.call_count == 2
    assert mock_wled.listen.call_count == 2
    assert mock_wled.disconnect.call_count == 1

    # Resolve Future with a connection losed.
    connection_finished.set_exception(WLEDConnectionClosed)
    await hass.async_block_till_done()

    # Disconnect called
    assert mock_wled.disconnect.call_count == 2
