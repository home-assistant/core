"""Test the ESPHome bluetooth integration."""

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from ..conftest import MockESPHomeDevice


async def test_bluetooth_connect(
    hass: HomeAssistant, mock_bluetooth_entry_with_raw_adv: MockESPHomeDevice
) -> None:
    """Test bluetooth connect."""
    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:aa")
    assert scanner is not None
    assert scanner.connectable is True
    assert scanner.scanning is True
    assert scanner.connector.can_connect() is False  # no connection slots
    await mock_bluetooth_entry_with_raw_adv.mock_disconnect(True)
    await hass.async_block_till_done()

    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:aa")
    assert scanner is None
    await mock_bluetooth_entry_with_raw_adv.mock_connect()
    await hass.async_block_till_done()
    scanner = bluetooth.async_scanner_by_source(hass, "11:22:33:44:55:aa")
    assert scanner.scanning is True
