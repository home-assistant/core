"""Tests for the SMLIGHT Bluetooth platform."""

from unittest.mock import ANY, MagicMock

from pysmlight import Info
from pysmlight.models import BleFeatures
import pytest

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.smlight.bluetooth import get_ble_scanner_mode
from homeassistant.components.smlight.const import CONF_BLE_SCANNER_MODE, BLEScannerMode
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ultima_client")
async def test_bluetooth_scanner_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_scanner: MagicMock,
    mock_bluetooth_scanner: MagicMock,
) -> None:
    """Test setting up and unloading SMLIGHT Bluetooth scanner (lifecycle)."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_connect_scanner.assert_called_once_with(
        source=mock_config_entry.unique_id,
        name=mock_config_entry.title,
        host=mock_config_entry.data[CONF_HOST],
        port=5050,
    )

    client_data = mock_connect_scanner.return_value
    client_data.scanner.async_set_scanning_mode.assert_called_once_with(
        BluetoothScanningMode.AUTO
    )
    client_data.client.start.assert_called_once()
    mock_bluetooth_scanner.assert_called_once_with(
        hass,
        client_data.scanner,
        source_domain="smlight",
        source_model="SLZB-Ultima3",
        source_config_entry_id=mock_config_entry.entry_id,
        source_device_id=ANY,
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    client_data.client.stop.assert_called_once()


async def test_bluetooth_not_started_for_disabled_settings(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_scanner: MagicMock,
    mock_smlight_client: MagicMock,
) -> None:
    """Test that bluetooth scanner is not started for SLZB device with disabled settings."""
    mock_smlight_client.get_info.side_effect = None
    mock_smlight_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-MR3U",
        u_device=True,
        ble=BleFeatures(proxy_enabled=False),
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_connect_scanner.assert_not_called()


@pytest.mark.usefixtures("mock_smlight_client")
async def test_bluetooth_not_started_for_classic_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_scanner: MagicMock,
) -> None:
    """Test that bluetooth scanner is not started for classic (non-U) devices."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry = mock_config_entry
    assert entry.state is ConfigEntryState.LOADED
    mock_connect_scanner.assert_not_called()

    coordinator = entry.runtime_data.data
    assert coordinator.data.info.ble is None


@pytest.mark.parametrize(
    "scanner_mode",
    [
        "auto",
        "active",
        "passive",
    ],
)
async def test_bluetooth_scanner_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_scanner: MagicMock,
    mock_ultima_client: MagicMock,
    scanner_mode: str,
) -> None:
    """Test SLZB BLE scanner options when proxy is expected to start."""
    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_BLE_SCANNER_MODE: scanner_mode},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_connect_scanner.assert_called_once_with(
        source=mock_config_entry.unique_id,
        name=mock_config_entry.title,
        host=mock_config_entry.data[CONF_HOST],
        port=5050,
    )
    client_data = mock_connect_scanner.return_value
    client_data.scanner.async_set_scanning_mode.assert_called_once_with(
        BluetoothScanningMode(scanner_mode)
    )
    mock_ultima_client.set_ble_proxy.assert_not_called()


async def test_bluetooth_scanner_options_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_scanner: MagicMock,
    mock_ultima_client: MagicMock,
) -> None:
    """Test SLZB BLE scanner options when the scanner mode is disabled."""
    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_BLE_SCANNER_MODE: "disabled"},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_connect_scanner.assert_not_called()
    mock_ultima_client.set_ble_proxy.assert_not_called()


async def test_bluetooth_scanner_options_device_proxy_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect_scanner: MagicMock,
    mock_ultima_client: MagicMock,
) -> None:
    """Test SLZB BLE scanner options when device proxy is disabled on the hardware."""
    mock_ultima_client.get_info.side_effect = None
    mock_ultima_client.get_info.return_value = Info(
        MAC="AA:BB:CC:DD:EE:FF",
        model="SLZB-Ultima3",
        ble=BleFeatures(ble_enabled=True, proxy_enabled=False),
    )

    mock_config_entry.add_to_hass(hass)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_BLE_SCANNER_MODE: "passive"},
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_connect_scanner.assert_not_called()
    mock_ultima_client.set_ble_proxy.assert_not_called()


async def test_get_ble_scanner_mode_no_ble(
    hass: HomeAssistant,
    mock_smlight_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test get_ble_scanner_mode when BLE is not supported by the hardware."""
    info = await mock_smlight_client.get_info()
    assert get_ble_scanner_mode(mock_config_entry, info) is BLEScannerMode.DISABLED
