"""Test setting up and unloading SteamVR Base Station."""

from datetime import timedelta
import time

import pytest

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from . import STATION_SERVICE_INFO, TEST_ADDRESS, TEST_NAME
from .conftest import DEVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info_bleak,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)

SWITCH = "switch.lhb_747a9bc5"


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test a station is set up and unloaded."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_until_in_range(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried while no scanner can see the station."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.reason is not None
    assert TEST_NAME in mock_config_entry.reason


async def test_device_info(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device shows the product name and the Device Information strings."""
    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, TEST_ADDRESS), init_integration.entry_id
    )
    assert device is not None
    assert device.name == TEST_NAME
    assert device.manufacturer == "Valve"
    assert device.model == "Base Station 2.0"
    assert device.model_id == DEVICE_INFO.model
    assert device.sw_version == DEVICE_INFO.firmware
    assert device.hw_version == DEVICE_INFO.hardware
    assert device.serial_number == DEVICE_INFO.serial


@pytest.mark.usefixtures("station_in_range", "device_info_unreachable")
async def test_setup_retries_when_unreachable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup is retried when the station does not accept a connection."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_unavailable_and_recovery(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test the station goes unavailable without advertisements and recovers."""
    assert hass.states.get(SWITCH).state == STATE_ON

    stale = FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1
    with (
        patch_bluetooth_time(time.monotonic() + stale),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=stale))
        await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == STATE_UNAVAILABLE
    assert f"{TEST_NAME} is unavailable" in caplog.text

    inject_bluetooth_service_info_bleak(hass, STATION_SERVICE_INFO)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == STATE_ON
    assert f"{TEST_NAME} is available again" in caplog.text
