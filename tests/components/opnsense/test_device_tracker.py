"""The tests for the opnsense device tracker platform."""

from unittest.mock import patch

from homeassistant.components.opnsense.device_tracker import async_get_scanner
from homeassistant.core import HomeAssistant

from . import setup_mock_diagnostics

from tests.common import MockConfigEntry


async def test_get_scanner(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test creating an opnsense scanner."""

    with patch("homeassistant.components.opnsense.diagnostics") as mock_diagnostics:
        setup_mock_diagnostics(mock_diagnostics)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    scanner = await async_get_scanner(hass, {})
    assert scanner is not None

    # With no specific tracker interfaces configured, all devices should be returned
    devices = scanner.scan_devices()
    assert len(devices) == 2
    assert "ff:ff:ff:ff:ff:ff" in devices
    assert "ff:ff:ff:ff:ff:fe" in devices
