"""Test the Nespresso init."""

from unittest.mock import AsyncMock, patch

from bleak import BleakError
from nespresso_ble import MachineStatus

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import SERVICE_INFO, make_device

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_update_device: AsyncMock,
) -> None:
    """Test setting up and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, SERVICE_INFO)

    with patch(
        "homeassistant.components.nespresso_ble.coordinator.bluetooth.async_ble_device_from_address",
        return_value=SERVICE_INFO.device,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_no_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_update_device: AsyncMock,
) -> None:
    """Test setup retries when the BLE device is not found."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.nespresso_ble.coordinator.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_update_device: AsyncMock,
) -> None:
    """Test setup retries when reading the machine fails."""
    mock_config_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, SERVICE_INFO)
    mock_update_device.side_effect = BleakError("boom")

    with patch(
        "homeassistant.components.nespresso_ble.coordinator.bluetooth.async_ble_device_from_address",
        return_value=SERVICE_INFO.device,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_push_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that push stream updates propagate to entities."""
    mock_config_entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, SERVICE_INFO)

    captured: dict[str, object] = {}

    async def fake_stream(ble_device, callback, stop_event):
        captured["callback"] = callback
        await stop_event.wait()

    with (
        patch(
            "homeassistant.components.nespresso_ble.coordinator.NespressoBluetoothDeviceData.update_device",
            return_value=make_device(),
        ),
        patch(
            "homeassistant.components.nespresso_ble.coordinator.NespressoBluetoothDeviceData.supports_push",
            return_value=True,
        ),
        patch(
            "homeassistant.components.nespresso_ble.coordinator.NespressoBluetoothDeviceData.stream",
            side_effect=fake_stream,
        ),
        patch(
            "homeassistant.components.nespresso_ble.coordinator.bluetooth.async_ble_device_from_address",
            return_value=SERVICE_INFO.device,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.nespresso_vertuo_mini_machine_status").state
            == "ready"
        )

        updated = make_device()
        updated.status = MachineStatus.BREWING
        captured["callback"](updated)
        await hass.async_block_till_done()

        assert (
            hass.states.get("sensor.nespresso_vertuo_mini_machine_status").state
            == "brewing"
        )
