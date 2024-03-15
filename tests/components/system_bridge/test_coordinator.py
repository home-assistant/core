"""Test the System Bridge coordinator."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock

from systembridgemodels.const import (
    MODEL_BATTERY,
    MODEL_CPU,
    MODEL_DISKS,
    MODEL_DISPLAYS,
    MODEL_GPUS,
    MODEL_MEDIA,
    MODEL_MEMORY,
    MODEL_PROCESSES,
    MODEL_SYSTEM,
)
from systembridgemodels.fixtures.modules.battery import FIXTURE_BATTERY
from systembridgemodels.fixtures.modules.cpu import FIXTURE_CPU
from systembridgemodels.fixtures.modules.disks import FIXTURE_DISKS
from systembridgemodels.fixtures.modules.displays import FIXTURE_DISPLAYS
from systembridgemodels.fixtures.modules.gpus import FIXTURE_GPUS
from systembridgemodels.fixtures.modules.media import FIXTURE_MEDIA
from systembridgemodels.fixtures.modules.memory import FIXTURE_MEMORY
from systembridgemodels.fixtures.modules.processes import FIXTURE_PROCESSES
from systembridgemodels.fixtures.modules.system import FIXTURE_SYSTEM

from homeassistant.components.system_bridge.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_websocket(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_websocket_client: MagicMock,
) -> None:
    """Test WebSocket connection."""
    assert mock_websocket_client.connect.call_count == 0
    assert mock_websocket_client.listen.call_count == 0
    assert mock_websocket_client.close.call_count == 0

    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(
        callback: Callable[[str, Any], Awaitable[None]],
        _: bool = False,
    ):
        connection_connected.set_result(callback)
        await connection_finished

    # Mock listener with a Future
    mock_websocket_client.listen.side_effect = connect

    # Mock out the event bus
    mock_bus = MagicMock()
    hass.bus = mock_bus

    # Next refresh it should connect
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    callback = await connection_connected
    await callback(MODEL_BATTERY, FIXTURE_BATTERY)
    await callback(MODEL_CPU, FIXTURE_CPU)
    await callback(MODEL_DISKS, FIXTURE_DISKS)
    await callback(MODEL_DISPLAYS, FIXTURE_DISPLAYS)
    await callback(MODEL_GPUS, FIXTURE_GPUS)
    await callback(MODEL_MEDIA, FIXTURE_MEDIA)
    await callback(MODEL_MEMORY, FIXTURE_MEMORY)
    await callback(MODEL_PROCESSES, FIXTURE_PROCESSES)
    await callback(MODEL_SYSTEM, FIXTURE_SYSTEM)

    # with patch(
    #     "systembridgeconnector.version.Version.check_supported",
    #     return_value=True,
    # ) as mock_check_supported:
    #     mock_config_entry.add_to_hass(hass)
    #     await hass.config_entries.async_setup(mock_config_entry.entry_id)
    # #     await hass.async_block_till_done()

    # assert mock_config_entry.state == ConfigEntryState.LOADED
