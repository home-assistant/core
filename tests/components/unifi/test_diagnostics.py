"""Test UniFi Network diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

CLIENT_DATA = [
    {
        "blocked": False,
        "hostname": "client_1",
        "ip": "10.0.0.1",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
        "name": "POE Client 1",
        "oui": "Producer",
        "sw_mac": "00:00:00:00:01:01",
        "sw_port": 1,
        "wired-rx_bytes": 1234000000,
        "wired-tx_bytes": 5678000000,
    }
]
DEVICE_DATA = [
    {
        "board_rev": "1.2.3",
        "ethernet_table": [
            {
                "mac": "22:22:22:22:22:22",
                "num_port": 2,
                "name": "eth0",
            }
        ],
        "device_id": "mock-id",
        "ip": "10.0.1.1",
        "mac": "00:00:00:00:01:01",
        "last_seen": 1562600145,
        "model": "US16P150",
        "name": "mock-name",
        "port_overrides": [],
        "port_table": [
            {
                "mac_table": [
                    {
                        "age": 1,
                        "mac": "00:00:00:00:00:01",
                        "static": False,
                        "uptime": 3971792,
                        "vlan": 1,
                    },
                    {
                        "age": 1,
                        "mac": "11:11:11:11:11:11",
                        "static": True,
                        "uptime": 0,
                        "vlan": 0,
                    },
                ],
                "media": "GE",
                "name": "Port 1",
                "port_idx": 1,
                "poe_class": "Class 4",
                "poe_enable": True,
                "poe_mode": "auto",
                "poe_power": "2.56",
                "poe_voltage": "53.40",
                "portconf_id": "1a1",
                "port_poe": True,
                "up": True,
            },
        ],
        "state": 1,
        "type": "usw",
        "version": "4.0.42.10433",
    }
]
DPI_APP_DATA = [
    {
        "_id": "5f976f62e3c58f018ec7e17d",
        "apps": [],
        "blocked": True,
        "cats": ["4"],
        "enabled": True,
        "log": True,
        "site_id": "name",
    }
]
DPI_GROUP_DATA = [
    {
        "_id": "5f976f4ae3c58f018ec7dff6",
        "name": "Block Media Streaming",
        "site_id": "name",
        "dpiapp_ids": ["5f976f62e3c58f018ec7e17d"],
    }
]


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
            CONF_BLOCK_CLIENT: ["00:00:00:00:00:01"],
        }
    ],
)
@pytest.mark.parametrize("client_payload", [CLIENT_DATA])
@pytest.mark.parametrize("device_payload", [DEVICE_DATA])
@pytest.mark.parametrize("dpi_app_payload", [DPI_APP_DATA])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUP_DATA])
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_setup: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_setup
    ) == snapshot(exclude=props("created_at", "modified_at"))
