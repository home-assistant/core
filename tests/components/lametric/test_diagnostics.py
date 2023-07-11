"""Tests for the diagnostics data provided by the LaMetric integration."""

from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "device_id": REDACTED,
        "name": REDACTED,
        "serial_number": REDACTED,
        "os_version": "2.2.2",
        "mode": "auto",
        "model": "LM 37X8",
        "audio": {
            "volume": 100,
            "volume_range": {"range_min": 0, "range_max": 100},
            "volume_limit": {"range_min": 0, "range_max": 100},
        },
        "bluetooth": {
            "available": True,
            "name": REDACTED,
            "active": False,
            "discoverable": True,
            "pairable": True,
            "address": "AA:BB:CC:DD:EE:FF",
        },
        "display": {
            "brightness": 100,
            "brightness_mode": "auto",
            "width": 37,
            "height": 8,
            "display_type": "mixed",
        },
        "wifi": {
            "active": True,
            "mac": "AA:BB:CC:DD:EE:FF",
            "available": True,
            "encryption": "WPA",
            "ssid": REDACTED,
            "ip": "127.0.0.1",
            "mode": "dhcp",
            "netmask": "255.255.255.0",
            "rssi": 21,
        },
    }
