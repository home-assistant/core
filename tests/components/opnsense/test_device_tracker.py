"""The tests for the opnsense device tracker platform."""

from unittest import mock

import pytest

from homeassistant.components.opnsense.const import (
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from homeassistant.components.opnsense.device_tracker import (
    OPNsenseDeviceScanner,
    async_setup_scanner,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def test_get_scanner() -> None:
    """Test creating an OPNsense scanner and reading device data."""
    interface_client = mock.MagicMock()
    interface_client.get_arp.return_value = [
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

    scanner = OPNsenseDeviceScanner(interface_client, ["LAN"])

    assert scanner.scan_devices() == ["ff:ff:ff:ff:ff:ff", "ff:ff:ff:ff:ff:fe"]
    assert scanner.get_device_name("ff:ff:ff:ff:ff:fe") == "Desktop"
    assert scanner.get_device_name("ff:ff:ff:ff:ff:ff") is None
    assert scanner.get_device_name("ff:ff:ff:ff:ff:fd") is None
    assert scanner.get_extra_attributes("ff:ff:ff:ff:ff:ff") == {}
    assert scanner.get_extra_attributes("ff:ff:ff:ff:ff:fe") == {"manufacturer": "OEM"}
    assert scanner.get_extra_attributes("ff:ff:ff:ff:ff:fd") == {}


async def test_async_setup_scanner_no_runtime_data(
    hass: HomeAssistant,
) -> None:
    """async_setup_scanner returns False when no runtime_data exists."""
    assert not await async_setup_scanner(hass, {}, mock.AsyncMock())


async def test_async_setup_scanner_uses_discovery_entry_id(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """async_setup_scanner uses runtime_data from matching discovery entry_id."""
    first_client = mock.MagicMock()
    second_client = mock.MagicMock()

    first_entry = MockConfigEntry(domain=DOMAIN, data={})
    first_entry.runtime_data = {
        CONF_INTERFACE_CLIENT: first_client,
        CONF_TRACKER_INTERFACES: ["FIRST"],
    }
    first_entry.add_to_hass(hass)

    second_entry = MockConfigEntry(domain=DOMAIN, data={})
    second_entry.runtime_data = {
        CONF_INTERFACE_CLIENT: second_client,
        CONF_TRACKER_INTERFACES: ["SECOND"],
    }
    second_entry.add_to_hass(hass)

    setup_scanner_platform = mock.MagicMock()
    monkeypatch.setattr(
        "homeassistant.components.opnsense.device_tracker.async_setup_scanner_platform",
        setup_scanner_platform,
    )

    assert await async_setup_scanner(
        hass,
        {},
        mock.AsyncMock(),
        {"entry_id": second_entry.entry_id},
    )

    scanner = setup_scanner_platform.call_args.args[2]
    assert isinstance(scanner, OPNsenseDeviceScanner)
    assert scanner.client is second_client
    assert scanner.interfaces == ["SECOND"]
