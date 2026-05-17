"""Test AirTouch 3 discovery helpers."""

from ipaddress import IPv4Address
from unittest.mock import patch

from homeassistant.components.airtouch3.discovery import (
    _async_get_discovery_targets,
    _parse_discovery_payload,
)
from homeassistant.core import HomeAssistant


def test_parse_discovery_payload() -> None:
    """Test parsing an AirTouch 3 UDP discovery reply."""
    discovery = _parse_discovery_payload(b"10.200.5.20,F0FE6B772324,AirTouch3")

    assert discovery
    assert discovery.host == "10.200.5.20"
    assert discovery.mac == "F0FE6B772324"
    assert discovery.model == "AirTouch3"


def test_parse_discovery_payload_rejects_other_models() -> None:
    """Test discovery ignores non-AirTouch replies."""
    assert _parse_discovery_payload(b"10.200.5.20,F0FE6B772324,Other") is None
    assert _parse_discovery_payload(b"HF-A11ASSISTHREAD") is None
    assert _parse_discovery_payload(b"not-an-ip,F0FE6B772324,AirTouch3") is None


async def test_async_get_discovery_targets_includes_adapter_broadcasts(
    hass: HomeAssistant,
) -> None:
    """Test discovery targets include broadcast addresses from enabled adapters."""
    with (
        patch(
            "homeassistant.components.airtouch3.discovery.network.async_get_ipv4_broadcast_addresses",
            return_value={IPv4Address("255.255.255.255")},
        ),
        patch(
            "homeassistant.components.airtouch3.discovery.network.async_get_adapters",
            return_value=[
                {
                    "auto": True,
                    "default": True,
                    "enabled": True,
                    "index": 1,
                    "ipv4": [{"address": "10.200.6.240", "network_prefix": 24}],
                    "ipv6": [],
                    "name": "eth0",
                },
                {
                    "auto": False,
                    "default": False,
                    "enabled": False,
                    "index": 2,
                    "ipv4": [{"address": "10.200.5.100", "network_prefix": 24}],
                    "ipv6": [],
                    "name": "eth1",
                },
            ],
        ),
    ):
        assert await _async_get_discovery_targets(hass) == [
            "10.200.6.255",
            "255.255.255.255",
        ]
