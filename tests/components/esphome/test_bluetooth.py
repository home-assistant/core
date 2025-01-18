"""Test the ESPHome bluetooth integration."""

from unittest.mock import patch

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDevice


async def test_bluetooth_connect_with_raw_adv(
    hass: HomeAssistant, mock_bluetooth_entry_with_raw_adv: MockESPHomeDevice
) -> None:
    """Test bluetooth connect with raw advertisements."""
    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:AA")
    assert scanner is not None
    assert scanner.connectable is True
    assert scanner.scanning is True
    assert scanner.connector.can_connect() is False  # no connection slots
    await mock_bluetooth_entry_with_raw_adv.mock_disconnect(True)
    await hass.async_block_till_done()

    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:AA")
    assert scanner is None
    await mock_bluetooth_entry_with_raw_adv.mock_connect()
    await hass.async_block_till_done()
    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:AA")
    assert scanner.scanning is True


async def test_bluetooth_connect_with_legacy_adv(
    hass: HomeAssistant, mock_bluetooth_entry_with_legacy_adv: MockESPHomeDevice
) -> None:
    """Test bluetooth connect with legacy advertisements."""
    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:AA")
    assert scanner is not None
    assert scanner.connectable is True
    assert scanner.scanning is True
    assert scanner.connector.can_connect() is False  # no connection slots
    await mock_bluetooth_entry_with_legacy_adv.mock_disconnect(True)
    await hass.async_block_till_done()

    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:AA")
    assert scanner is None
    await mock_bluetooth_entry_with_legacy_adv.mock_connect()
    await hass.async_block_till_done()
    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:AA")
    assert scanner.scanning is True


async def test_bluetooth_cleanup_on_remove_entry(
    hass: HomeAssistant, mock_bluetooth_entry_with_raw_adv: MockESPHomeDevice
) -> None:
    """Test bluetooth is cleaned up on entry removal."""
    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:AA")
    assert scanner.connectable is True
    await hass.config_entries.async_unload(
        mock_bluetooth_entry_with_raw_adv.entry.entry_id
    )

    with patch("homeassistant.components.esphome.async_remove_scanner") as remove_mock:
        await hass.config_entries.async_remove(
            mock_bluetooth_entry_with_raw_adv.entry.entry_id
        )
        await hass.async_block_till_done()

    remove_mock.assert_called_once_with(hass, scanner.source)
