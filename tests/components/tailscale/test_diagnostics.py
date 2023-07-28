"""Tests for the diagnostics data provided by the Tailscale integration."""

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
        "devices": [
            {
                "addresses": REDACTED,
                "device_id": REDACTED,
                "user": REDACTED,
                "name": REDACTED,
                "hostname": REDACTED,
                "client_version": "1.12.3-td91ea7286-ge1bbbd90c",
                "update_available": True,
                "os": "iOS",
                "created": "2021-08-19T09:25:22+00:00",
                "last_seen": "2021-09-16T06:11:23+00:00",
                "key_expiry_disabled": False,
                "expires": "2022-02-15T09:25:22+00:00",
                "authorized": True,
                "is_external": False,
                "machine_key": REDACTED,
                "node_key": REDACTED,
                "blocks_incoming_connections": False,
                "enabled_routes": [],
                "advertised_routes": [],
                "client_connectivity": {
                    "endpoints": REDACTED,
                    "derp": "",
                    "mapping_varies_by_dest_ip": False,
                    "latency": {},
                    "client_supports": {
                        "hair_pinning": False,
                        "ipv6": False,
                        "pcp": False,
                        "pmp": False,
                        "udp": True,
                        "upnp": False,
                    },
                },
            },
            {
                "addresses": REDACTED,
                "device_id": REDACTED,
                "user": REDACTED,
                "name": REDACTED,
                "hostname": REDACTED,
                "client_version": "1.14.0-t5cff36945-g809e87bba",
                "update_available": True,
                "os": "linux",
                "created": "2021-08-29T09:49:06+00:00",
                "last_seen": "2021-11-15T20:37:03+00:00",
                "key_expiry_disabled": False,
                "expires": "2022-02-25T09:49:06+00:00",
                "authorized": True,
                "is_external": False,
                "machine_key": REDACTED,
                "node_key": REDACTED,
                "blocks_incoming_connections": False,
                "enabled_routes": ["0.0.0.0/0", "10.10.10.0/23", "::/0"],
                "advertised_routes": ["0.0.0.0/0", "10.10.10.0/23", "::/0"],
                "client_connectivity": {
                    "endpoints": REDACTED,
                    "derp": "",
                    "mapping_varies_by_dest_ip": False,
                    "latency": {
                        "Bangalore": {"latencyMs": 143.42505599999998},
                        "Chicago": {"latencyMs": 101.123646},
                        "Dallas": {"latencyMs": 136.85886},
                        "Frankfurt": {"latencyMs": 18.968314},
                        "London": {"preferred": True, "latencyMs": 14.314574},
                        "New York City": {"latencyMs": 83.078912},
                        "San Francisco": {"latencyMs": 148.215522},
                        "Seattle": {"latencyMs": 181.553595},
                        "Singapore": {"latencyMs": 164.566539},
                        "São Paulo": {"latencyMs": 207.250179},
                        "Tokyo": {"latencyMs": 226.90714300000002},
                    },
                    "client_supports": {
                        "hair_pinning": True,
                        "ipv6": False,
                        "pcp": False,
                        "pmp": False,
                        "udp": True,
                        "upnp": False,
                    },
                },
            },
        ]
    }
