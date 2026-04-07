"""The tests for the opnsense device tracker platform."""

from unittest.mock import patch

from homeassistant.components.opnsense.device_tracker import async_get_scanner
from homeassistant.core import HomeAssistant

from . import setup_mock_diagnostics

@pytest.fixture(name="mocked_opnsense")
def mocked_opnsense():
    """Mock for aiopnsense.OPNsenseClient."""
    with mock.patch.object(opnsense, "OPNsenseClient") as mocked_opn:
        yield mocked_opn


async def test_get_scanner(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test creating an opnsense scanner."""
    opnsense_client = mock.AsyncMock()
    mocked_opnsense.return_value = opnsense_client
    opnsense_client.get_arp_table.return_value = [
        {
            "hostname": "",
            "intf": "igb1",
            "intf_description": "LAN",
            "ip": "192.168.0.123",
            "mac": "ff:ff:ff:ff:ff:ff",
            "manufacturer": "",
        },
        {
            "hostname": "Desktop",
            "intf": "igb1",
            "intf_description": "LAN",
            "ip": "192.168.0.167",
            "mac": "ff:ff:ff:ff:ff:fe",
            "manufacturer": "OEM",
        },
    ]

    opnsense_client.get_interfaces.return_value = {
        "wan": {"name": "WAN"},
        "lan": {"name": "LAN"},
    }

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
