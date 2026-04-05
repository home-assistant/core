"""Test the Teleinfo coordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

import serial

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_update_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test successful data update through the coordinator."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert coordinator.data is not None
    assert coordinator.data["ADCO"] == "021861348497"
    assert coordinator.data["PAPP"] == "02830"


async def test_update_serial_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test UpdateFailed on SerialException during update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    mock_serial_port.side_effect = serial.SerialException("device disconnected")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test UpdateFailed on TimeoutError during update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    mock_serial_port.side_effect = TimeoutError("no data")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_decode_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test UpdateFailed on decode failure during update."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    mock_teleinfo.decode.side_effect = RuntimeError("bad frame")
    await coordinator.async_refresh()

    assert coordinator.last_update_success is False


async def test_update_recovers_after_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teleinfo: MagicMock,
    mock_serial_port: MagicMock,
) -> None:
    """Test coordinator recovers after a transient error."""
    from .conftest import MOCK_DECODED_DATA, MOCK_FRAME  # noqa: PLC0415

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data

    # Simulate error
    mock_serial_port.side_effect = TimeoutError("transient")
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False

    # Recover
    mock_serial_port.side_effect = None
    mock_serial_port.return_value = MOCK_FRAME
    mock_teleinfo.decode.side_effect = None
    mock_teleinfo.decode.return_value = MOCK_DECODED_DATA
    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    assert coordinator.data["ADCO"] == "021861348497"
