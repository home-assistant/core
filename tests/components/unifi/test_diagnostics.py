"""Test UniFi Network diagnostics."""

from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_BLOCK_CLIENT,
)
from homeassistant.components.unifi.device_tracker import CLIENT_TRACKER, DEVICE_TRACKER
from homeassistant.components.unifi.sensor import RX_SENSOR, TX_SENSOR, UPTIME_SENSOR
from homeassistant.components.unifi.switch import BLOCK_SWITCH, DPI_SWITCH, POE_SWITCH
from homeassistant.const import Platform

from .test_controller import setup_unifi_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, hass_client, aioclient_mock):
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
        "device_id": "mock-id",
        "ip": "10.0.1.1",
        "mac": "00:00:00:00:01:01",
        "last_seen": 1562600145,
        "model": "US16P150",
        "name": "mock-name",
        "port_overrides": [],
        "port_table": [
            {
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
            {
                "media": "GE",
                "name": "Port 2",
                "port_idx": 2,
                "poe_class": "Class 4",
                "poe_enable": True,
                "poe_mode": "auto",
                "poe_power": "2.56",
                "poe_voltage": "53.40",
                "portconf_id": "1a2",
                "port_poe": True,
                "up": True,
            },
            {
                "media": "GE",
                "name": "Port 3",
                "port_idx": 3,
                "poe_class": "Unknown",
                "poe_enable": False,
                "poe_mode": "off",
                "poe_power": "0.00",
                "poe_voltage": "0.00",
                "portconf_id": "1a3",
                "port_poe": False,
                "up": True,
            },
            {
                "media": "GE",
                "name": "Port 4",
                "port_idx": 4,
                "poe_class": "Unknown",
                "poe_enable": False,
                "poe_mode": "auto",
                "poe_power": "0.00",
                "poe_voltage": "0.00",
                "portconf_id": "1a4",
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
        "config_entry": {
            "controller": "**REDACTED**",
            "host": "1.2.3.4",
            "password": "**REDACTED**",
            "port": 1234,
            "site": "site_id",
            "username": "username",
            "verify_ssl": False,
        },
        "site_role": "admin",
        "entities": {
            str(Platform.DEVICE_TRACKER): {
                CLIENT_TRACKER: ["00:00:00:00:00:01"],
                DEVICE_TRACKER: ["00:00:00:00:01:01"],
            },
            str(Platform.SENSOR): {
                RX_SENSOR: ["00:00:00:00:00:01"],
                TX_SENSOR: ["00:00:00:00:00:01"],
                UPTIME_SENSOR: ["00:00:00:00:00:01"],
            },
            str(Platform.SWITCH): {
                BLOCK_SWITCH: ["00:00:00:00:00:01"],
                DPI_SWITCH: ["5f976f4ae3c58f018ec7dff6"],
                POE_SWITCH: ["00:00:00:00:00:01"],
            },
        },
        "clients": {
            "00:00:00:00:00:01": {
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
        },
        "devices": {
            "00:00:00:00:01:01": {
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": "00:00:00:00:01:01",
                "last_seen": 1562600145,
                "model": "US16P150",
                "name": "mock-name",
                "port_overrides": [],
                "port_table": [
                    {
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
                    {
                        "media": "GE",
                        "name": "Port 2",
                        "port_idx": 2,
                        "poe_class": "Class 4",
                        "poe_enable": True,
                        "poe_mode": "auto",
                        "poe_power": "2.56",
                        "poe_voltage": "53.40",
                        "portconf_id": "1a2",
                        "port_poe": True,
                        "up": True,
                    },
                    {
                        "media": "GE",
                        "name": "Port 3",
                        "port_idx": 3,
                        "poe_class": "Unknown",
                        "poe_enable": False,
                        "poe_mode": "off",
                        "poe_power": "0.00",
                        "poe_voltage": "0.00",
                        "portconf_id": "1a3",
                        "port_poe": False,
                        "up": True,
                    },
                    {
                        "media": "GE",
                        "name": "Port 4",
                        "port_idx": 4,
                        "poe_class": "Unknown",
                        "poe_enable": False,
                        "poe_mode": "auto",
                        "poe_power": "0.00",
                        "poe_voltage": "0.00",
                        "portconf_id": "1a4",
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
