"""Test the System Bridge integration."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

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

from homeassistant.components.system_bridge.config_flow import SystemBridgeConfigFlow
from homeassistant.components.system_bridge.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import FIXTURE_USER_INPUT, FIXTURE_UUID, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_websocket_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
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

    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

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

    assert entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_migration_minor_1_to_2(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test migration."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data={
            CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
            CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
            CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        },
        version=SystemBridgeConfigFlow.VERSION,
        minor_version=1,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1

    # Check that the version has been updated and the api_key has been moved to token
    assert config_entry.version == SystemBridgeConfigFlow.VERSION
    assert config_entry.minor_version == SystemBridgeConfigFlow.MINOR_VERSION
    assert config_entry.data == {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    assert config_entry.state == ConfigEntryState.LOADED


async def test_migration_minor_future_version(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test migration."""
    config_entry_data = {
        CONF_API_KEY: FIXTURE_USER_INPUT[CONF_TOKEN],
        CONF_HOST: FIXTURE_USER_INPUT[CONF_HOST],
        CONF_PORT: FIXTURE_USER_INPUT[CONF_PORT],
        CONF_TOKEN: FIXTURE_USER_INPUT[CONF_TOKEN],
    }
    config_entry_version = SystemBridgeConfigFlow.VERSION
    config_entry_minor_version = SystemBridgeConfigFlow.MINOR_VERSION + 1
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UUID,
        data=config_entry_data,
        version=config_entry_version,
        minor_version=config_entry_minor_version,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1

    assert config_entry.version == config_entry_version
    assert config_entry.minor_version == config_entry_minor_version
    assert config_entry.data == config_entry_data
    assert config_entry.state == ConfigEntryState.LOADED
