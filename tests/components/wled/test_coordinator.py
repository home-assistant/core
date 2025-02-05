"""Tests for the coordinator of the WLED integration."""

import asyncio
from collections.abc import Callable
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from wled import (
    Device as WLEDDevice,
    WLEDConnectionClosedError,
    WLEDConnectionError,
    WLEDError,
)

from homeassistant.components.wled.const import SCAN_INTERVAL
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_not_supporting_websocket(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Ensure no WebSocket attempt is made if non-WebSocket device."""
    assert mock_wled.connect.call_count == 0


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket_already_connected(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Ensure no a second WebSocket connection is made, if already connected."""
    assert mock_wled.connect.call_count == 1

    mock_wled.connected = True
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert mock_wled.connect.call_count == 1


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
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


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test WebSocket connection."""
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_ON

    # There is no Future in place yet...
    assert mock_wled.connect.call_count == 1
    assert mock_wled.listen.call_count == 1
    assert mock_wled.disconnect.call_count == 1

    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable[[WLEDDevice], None]):
        connection_connected.set_result(callback)
        await connection_finished

    # Mock out wled.listen with a Future
    mock_wled.listen.side_effect = connect

    # Mock out the event bus
    mock_bus = MagicMock()
    hass.bus = mock_bus

    # Next refresh it should connect
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    callback = await connection_connected

    # Connected to WebSocket, disconnect not called
    # listening for Home Assistant to stop
    assert mock_wled.connect.call_count == 2
    assert mock_wled.listen.call_count == 2
    assert mock_wled.disconnect.call_count == 1
    assert mock_bus.async_listen_once.call_count == 1
    assert (
        mock_bus.async_listen_once.call_args_list[0][0][0] == EVENT_HOMEASSISTANT_STOP
    )
    assert (
        mock_bus.async_listen_once.call_args_list[0][0][1].__name__ == "close_websocket"
    )
    assert mock_bus.async_listen_once.return_value.call_count == 0

    # Send update from WebSocket
    updated_device = deepcopy(mock_wled.update.return_value)
    updated_device.state.on = False
    callback(updated_device)
    await hass.async_block_till_done()

    # Check if entity updated
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_OFF

    # Resolve Future with a connection losed.
    connection_finished.set_exception(WLEDConnectionClosedError)
    await hass.async_block_till_done()

    # Disconnect called, unsubbed Home Assistant stop listener
    assert mock_wled.disconnect.call_count == 2
    assert mock_bus.async_listen_once.return_value.call_count == 1

    # Light still available, as polling takes over
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_OFF


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test WebSocket connection erroring out, marking lights unavailable."""
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_ON

    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable[[WLEDDevice], None]):
        connection_connected.set_result(None)
        await connection_finished

    mock_wled.listen.side_effect = connect
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await connection_connected

    # Resolve Future with an error.
    connection_finished.set_exception(WLEDError)
    await hass.async_block_till_done()

    # Light no longer available as an error occurred
    state = hass.states.get("light.wled_websocket")
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_websocket_disconnect_on_home_assistant_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Ensure WebSocket is disconnected when Home Assistant stops."""
    assert mock_wled.disconnect.call_count == 1
    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable[[WLEDDevice], None]):
        connection_connected.set_result(None)
        await connection_finished

    mock_wled.listen.side_effect = connect
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await connection_connected

    assert mock_wled.disconnect.call_count == 1

    hass.bus.fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert mock_wled.disconnect.call_count == 2
