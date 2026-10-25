"""Tests for the Tile BLE device tracker."""

from collections.abc import Generator
from datetime import timedelta
import time
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import TILE_ADDRESS, TILE_SERVICE_INFO, setup_integration

ENTITY_ID = "device_tracker.tile"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the device tracker platform."""
    with patch(
        "homeassistant.components.tile_ble.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        yield


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device tracker and its device."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, TILE_ADDRESS), mock_config_entry.entry_id
    )
    assert device == snapshot


async def test_already_home(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a Tile that is in range at startup is home."""
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_HOME


async def test_arrive_and_leave(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a Tile is home while it advertises and away once it stops."""
    start_monotonic = time.monotonic()
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_NOT_HOME

    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_HOME

    offset = FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    with (
        patch_bluetooth_time(start_monotonic + offset),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=offset))
        await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_NOT_HOME
