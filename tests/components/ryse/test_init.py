"""Tests for RYSE init setup."""

import logging
from unittest.mock import MagicMock

from bleak import BleakError
from bleak.backends.device import BLEDevice
import pytest

from homeassistant.components.ryse.const import DATA_LOCAL_WAITERS, SERVICE_UUID
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import (
    DEVICE_ADDRESS,
    make_advertisement,
    make_ble_device,
    register_local_scanner,
    register_remote_scanner,
)

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test integration setup and unload."""
    assert setup_integration.state is ConfigEntryState.LOADED
    mock_device.pair.assert_awaited_once()

    await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    mock_device.unpair.assert_awaited_once()


async def test_unload_succeeds_when_unpair_fails(
    hass: HomeAssistant,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test a disconnect error during unload does not fail the config entry."""
    mock_device.unpair.side_effect = BleakError("already gone")

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert setup_integration.state is ConfigEntryState.NOT_LOADED
    mock_device.unpair.assert_awaited_once()


async def test_setup_passes_resolved_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ryse_ble_device: MagicMock,
    local_ble_device: BLEDevice,
    local_ryse_scanner: BLEDevice,
) -> None:
    """Test setup passes the Home Assistant-resolved BLEDevice to ryseble."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_ryse_ble_device.assert_called_once_with(local_ble_device)


async def test_setup_without_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup is retried when the device is not seen by the bluetooth stack."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retries_when_pairing_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_ryse_scanner: BLEDevice,
    mock_device: MagicMock,
) -> None:
    """Test setup is retried when pairing with the device fails."""
    mock_device.pair.return_value = False
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_device.unpair.assert_awaited_once()


async def test_setup_retries_on_ble_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_ryse_scanner: BLEDevice,
    mock_device: MagicMock,
) -> None:
    """Test setup is retried when pairing raises a BLE error."""
    mock_device.pair.side_effect = BleakError("ble err")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_device.unpair.assert_awaited_once()


@pytest.mark.parametrize(
    "pair_side_effect",
    [
        pytest.param(False, id="pair_returns_false"),
        pytest.param(BleakError("ble err"), id="pair_raises"),
    ],
)
@pytest.mark.parametrize(
    "unpair_side_effect",
    [
        pytest.param(BleakError("unpair err"), id="unpair_bleak"),
        pytest.param(RuntimeError("unpair err"), id="unpair_unexpected"),
    ],
)
@pytest.mark.usefixtures("local_ryse_scanner")
async def test_setup_retries_when_unpair_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    pair_side_effect: bool | BleakError,
    unpair_side_effect: Exception,
) -> None:
    """Test setup is retried even if releasing the connection after a failed pair raises."""
    if pair_side_effect is False:
        mock_device.pair.return_value = False
    else:
        mock_device.pair.side_effect = pair_side_effect
    mock_device.unpair.side_effect = unpair_side_effect
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_device.unpair.assert_awaited_once()


async def test_setup_uses_local_adapter_not_proxy(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ryse_ble_device: MagicMock,
) -> None:
    """Test setup resolves the BLEDevice from a local adapter, not a proxy."""
    local_device = make_ble_device()
    advertisement = make_advertisement()
    proxy_device = make_ble_device()
    remote, cancel_remote = register_remote_scanner(hass)
    cancel_local = register_local_scanner(hass, local_device, advertisement)
    try:
        remote.inject_advertisement(proxy_device, advertisement)

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        mock_ryse_ble_device.assert_called_once_with(local_device)
    finally:
        cancel_local()
        cancel_remote()


async def test_ble_device_callback_keeps_local_route(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_ble_device: BLEDevice,
    local_ryse_scanner: BLEDevice,
    mock_device: MagicMock,
) -> None:
    """Test advertisement callbacks pin reconnects to a local adapter BLEDevice."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    advertisement = make_advertisement()
    proxy_device = make_ble_device()
    remote, cancel_remote = register_remote_scanner(hass)
    try:
        remote.inject_advertisement(proxy_device, advertisement)
        await hass.async_block_till_done()
        mock_device.set_ble_device.assert_called_with(local_ble_device)
    finally:
        cancel_remote()


async def test_ble_device_callback_logs_lost_and_restored_local_route(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_ble_device: BLEDevice,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the BLEDevice callback logs once when the local adapter route is lost and restored."""
    advertisement = make_advertisement()
    cancel_local = register_local_scanner(hass, local_ble_device, advertisement)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    remote, cancel_remote = register_remote_scanner(hass)
    try:
        cancel_local()
        with caplog.at_level(logging.INFO, logger="homeassistant.components.ryse"):
            remote.inject_advertisement(
                local_ble_device,
                make_advertisement(service_data={SERVICE_UUID: b"\x01"}),
            )
            await hass.async_block_till_done()
            remote.inject_advertisement(
                local_ble_device,
                make_advertisement(service_data={SERVICE_UUID: b"\x02"}),
            )
            await hass.async_block_till_done()

            lost = (
                f"No local Bluetooth adapter currently sees {DEVICE_ADDRESS}; "
                "commands require a local adapter, not a proxy"
            )
            assert caplog.text.count(lost) == 1
            mock_device.set_ble_device.assert_not_called()

            cancel_local = register_local_scanner(hass, local_ble_device, advertisement)
            remote.inject_advertisement(
                local_ble_device,
                make_advertisement(service_data={SERVICE_UUID: b"\x03"}),
            )
            await hass.async_block_till_done()
            restored = f"{DEVICE_ADDRESS} is visible on a local Bluetooth adapter again"
            assert caplog.text.count(restored) == 1
            mock_device.set_ble_device.assert_called_with(local_ble_device)
    finally:
        cancel_local()
        cancel_remote()


async def test_setup_cancels_proxy_waiter(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting up an entry drops a leftover proxy waiter."""
    device = make_ble_device()
    advertisement = make_advertisement()
    remote, cancel_remote = register_remote_scanner(hass)
    cancel_local = None
    try:
        remote.inject_advertisement(device, advertisement)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert DEVICE_ADDRESS in hass.data[DATA_LOCAL_WAITERS]

        cancel_local = register_local_scanner(hass, device, advertisement)
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert DEVICE_ADDRESS not in hass.data[DATA_LOCAL_WAITERS]
    finally:
        if cancel_local is not None:
            cancel_local()
        cancel_remote()
