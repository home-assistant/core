"""Tests for the SMLIGHT Bluetooth platform."""

from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.smlight.bluetooth import SmBleScanner
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ultima_client")
async def test_bluetooth_scanner_lifecycle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_client: MagicMock,
    mock_bluetooth_scanner: MagicMock,
) -> None:
    """Test setting up and unloading SMLIGHT Bluetooth scanner (lifecycle)."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_ble_client.return_value.start.assert_called_once()
    mock_bluetooth_scanner.assert_called_once_with(
        hass,
        ANY,
        source_domain="smlight",
        source_model="SLZB-Ultima3",
        source_config_entry_id=mock_config_entry.entry_id,
        source_device_id=ANY,
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_ble_client.return_value.stop.assert_called_once()


@pytest.mark.usefixtures("mock_ultima_client")
async def test_bluetooth_packet_forwarding(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_client: MagicMock,
) -> None:
    """Test SMLIGHT Bluetooth packet forwarding."""
    mock_config_entry.add_to_hass(hass)

    client_callback = None

    def save_callback(esp32_ip: str, callback: Any, esp32_port: int) -> MagicMock:
        nonlocal client_callback
        client_callback = callback
        mock_instance = MagicMock()
        mock_instance.start = AsyncMock()
        return mock_instance

    mock_ble_client.side_effect = save_callback

    with patch(
        "homeassistant.components.smlight.bluetooth.MONOTONIC_TIME",
        return_value=123.45,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert client_callback is not None

        with patch(
            "homeassistant.components.smlight.bluetooth.SmBleScanner._async_on_raw_advertisement"
        ) as mock_on_raw:
            client_callback("00:11:22:33:44:55", -85, 1, b"\x02\x01\x06")
            mock_on_raw.assert_called_once_with(
                address="00:11:22:33:44:55",
                rssi=-85,
                raw=b"\x02\x01\x06",
                details={"address_type": 1},
                advertisement_monotonic_time=123.45,
            )


@pytest.mark.usefixtures("mock_smlight_client")
async def test_bluetooth_not_started_for_classic_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_client: MagicMock,
) -> None:
    """Test that bluetooth scanner is not started for classic (non-U) devices."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_ble_client.assert_not_called()


async def test_bluetooth_start_client_none(hass: HomeAssistant) -> None:
    """Test start client when _client is None."""
    scanner = SmBleScanner(
        hass=hass,
        scanner_id="test_id",
        name="test_name",
        esp32_ip="1.2.3.4",
        esp32_port=1234,
    )
    assert scanner._client is None
    await scanner._async_start_client()
