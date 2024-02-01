"""Test UniFi Network diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
)
from homeassistant.core import HomeAssistant

from .test_controller import setup_unifi_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test config entry diagnostics."""
    client = {
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
    device = {
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
    dpi_app = {
        "_id": "5f976f62e3c58f018ec7e17d",
        "apps": [],
        "blocked": True,
        "cats": ["4"],
        "enabled": True,
        "log": True,
        "site_id": "name",
    }
    dpi_group = {
        "_id": "5f976f4ae3c58f018ec7dff6",
        "name": "Block Media Streaming",
        "site_id": "name",
        "dpiapp_ids": ["5f976f62e3c58f018ec7e17d"],
    }

    options = {
        CONF_ALLOW_BANDWIDTH_SENSORS: True,
        CONF_ALLOW_UPTIME_SENSORS: True,
        CONF_BLOCK_CLIENT: ["00:00:00:00:00:01"],
    }
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options=options,
        clients_response=[client],
        devices_response=[device],
        dpiapp_response=[dpi_app],
        dpigroup_response=[dpi_group],
    )

    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "config": {
            "data": {
                "host": REDACTED,
                "password": REDACTED,
                "port": 1234,
                "site": "site_id",
                "username": REDACTED,
                "verify_ssl": False,
            },
            "disabled_by": None,
            "domain": "unifi",
            "entry_id": "1",
            "minor_version": 1,
            "options": {
                "allow_bandwidth_sensors": True,
                "allow_uptime_sensors": True,
                "block_client": ["00:00:00:00:00:00"],
            },
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "title": "Mock Title",
            "unique_id": "1",
            "version": 1,
        },
        "role_is_admin": True,
        "clients": {
            "00:00:00:00:00:00": {
                "blocked": False,
                "hostname": "client_1",
                "ip": "10.0.0.1",
                "is_wired": True,
                "last_seen": 1562600145,
                "mac": "00:00:00:00:00:00",
                "name": "POE Client 1",
                "oui": "Producer",
                "sw_mac": "00:00:00:00:00:01",
                "sw_port": 1,
                "wired-rx_bytes": 1234000000,
                "wired-tx_bytes": 5678000000,
            }
        },
        "devices": {
            "00:00:00:00:00:01": {
                "board_rev": "1.2.3",
                "ethernet_table": [
                    {
                        "mac": "00:00:00:00:00:02",
                        "num_port": 2,
                        "name": "eth0",
                    }
                ],
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": "00:00:00:00:00:01",
                "last_seen": 1562600145,
                "model": "US16P150",
                "name": "mock-name",
                "port_overrides": [],
                "port_table": [
                    {
                        "mac_table": [
                            {
                                "age": 1,
                                "mac": "00:00:00:00:00:00",
                                "static": False,
                                "uptime": 3971792,
                                "vlan": 1,
                            },
                            {
                                "age": 1,
                                "mac": REDACTED,
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
        },
        "dpi_apps": {
            "5f976f62e3c58f018ec7e17d": {
                "_id": "5f976f62e3c58f018ec7e17d",
                "apps": [],
                "blocked": True,
                "cats": ["4"],
                "enabled": True,
                "log": True,
                "site_id": "name",
            }
        },
        "dpi_groups": {
            "5f976f4ae3c58f018ec7dff6": {
                "_id": "5f976f4ae3c58f018ec7dff6",
                "name": "Block Media Streaming",
                "site_id": "name",
                "dpiapp_ids": ["5f976f62e3c58f018ec7e17d"],
            }
        },
        "wlans": {},
    }
