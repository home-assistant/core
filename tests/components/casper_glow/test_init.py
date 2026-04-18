"""Test the Casper Glow integration init."""

from collections.abc import Generator
from datetime import timedelta
from itertools import count
from unittest.mock import MagicMock, patch

from bleak import BleakError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import format_mac
import homeassistant.util.dt as dt_util

from . import CASPER_GLOW_DISCOVERY_INFO, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)


async def test_async_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_async_setup_entry_device_not_found(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryNotReady when BLE device is not found."""
    mock_config_entry.add_to_hass(hass)

    # Do not inject BLE info — device is not in the cache
    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test unloading a config entry."""
    result = await hass.config_entries.async_unload(config_entry.entry_id)

    assert result is True
    assert config_entry.state == ConfigEntryState.NOT_LOADED


async def test_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device info is correctly populated."""
    device = device_registry.async_get_device(
        connections={
            (dr.CONNECTION_BLUETOOTH, format_mac(CASPER_GLOW_DISCOVERY_INFO.address))
        }
    )
    assert device is not None
    assert device == snapshot


_adv_counter = count(1)


@pytest.fixture(autouse=True)
def mock_monotonic() -> Generator[None]:
    """Patch monotonic_time_coarse to 0 so _last_poll is always falsy."""
    with patch(
        "homeassistant.components.casper_glow.coordinator.monotonic_time_coarse",
        return_value=0.0,
    ):
        yield


async def _trigger_poll(hass: HomeAssistant) -> None:
    """Trigger a debounced coordinator poll.

    Each call produces a unique manufacturer_data key so habluetooth's
    content-based deduplication (manufacturer_data / service_data /
    service_uuids / name) does not suppress the advertisement.
    """
    n = next(_adv_counter)
    inject_bluetooth_service_info(
        hass,
        BluetoothServiceInfoBleak(
            name="Jar",
            address="AA:BB:CC:DD:EE:FF",
            rssi=-60,
            manufacturer_data={n: b"\x01"},
            service_uuids=[],
            service_data={},
            source="local",
            device=generate_ble_device(address="AA:BB:CC:DD:EE:FF", name="Jar"),
            advertisement=generate_advertisement_data(
                manufacturer_data={n: b"\x01"}, service_uuids=[]
            ),
            time=0,
            connectable=True,
            tx_power=-127,
        ),
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))


async def test_poll_bleak_error_logs_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a BleakError during polling logs unavailable at info level once."""
    mock_casper_glow.query_state.side_effect = BleakError("connection failed")

    await _trigger_poll(hass)

    assert "Jar is unavailable" in caplog.text
    assert caplog.text.count("Jar is unavailable") == 1

    # A second poll failure must not log again
    caplog.clear()
    await _trigger_poll(hass)

    assert "Jar is unavailable" not in caplog.text


async def test_poll_generic_exception_logs_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a generic exception during polling logs an unexpected error."""
    mock_casper_glow.query_state.side_effect = Exception("unexpected")

    await _trigger_poll(hass)

    assert "unexpected error while polling" in caplog.text


async def test_poll_recovery_logs_back_online(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_casper_glow: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that recovery after a failed poll logs back online at info level."""
    mock_casper_glow.query_state.side_effect = BleakError("gone")

    await _trigger_poll(hass)

    assert "Jar is unavailable" in caplog.text
    caplog.clear()

    mock_casper_glow.query_state.side_effect = None
    await _trigger_poll(hass)

    assert "Jar is back online" in caplog.text
