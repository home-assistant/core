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
WLAN_DATA = [
    {
        "setting_preference": "manual",
        "wpa3_support": False,
        "dtim_6e": 3,
        "minrate_na_advertising_rates": False,
        "wpa_mode": "wpa2",
        "minrate_setting_preference": "auto",
        "minrate_ng_advertising_rates": False,
        "hotspot2conf_enabled": False,
        "radius_das_enabled": False,
        "mlo_enabled": False,
        "group_rekey": 3600,
        "radius_macacl_format": "none_lower",
        "pmf_mode": "disabled",
        "wpa3_transition": False,
        "passphrase_autogenerated": True,
        "private_preshared_keys": [
            {
                "password": "should be redacted",
                "networkconf_id": "67f2e03f7c572754fa1a2498",
            }
        ],
        "mcastenhance_enabled": False,
        "usergroup_id": "67f2e03f7c572754fa1a2499",
        "proxy_arp": False,
        "sae_sync": 5,
        "iapp_enabled": True,
        "uapsd_enabled": False,
        "enhanced_iot": False,
        "name": "devices",
        "site_id": "67f2e00e7c572754fa1a247e",
        "hide_ssid": False,
        "wlan_band": "2g",
        "_id": "67f2eaec026b2c2893c41b2a",
        "private_preshared_keys_enabled": True,
        "no2ghz_oui": True,
        "networkconf_id": "67f2e03f7c572754fa1a2498",
        "is_guest": False,
        "dtim_na": 3,
        "minrate_na_enabled": False,
        "sae_groups": [],
        "enabled": True,
        "sae_psk": [],
        "wlan_bands": ["2g"],
        "mac_filter_policy": "allow",
        "security": "wpapsk",
        "ap_group_ids": ["67f2e03f7c572754fa1a249e"],
        "l2_isolation": False,
        "minrate_ng_enabled": True,
        "bss_transition": True,
        "minrate_ng_data_rate_kbps": 1000,
        "radius_mac_auth_enabled": False,
        "schedule_with_duration": [],
        "wpa3_fast_roaming": False,
        "ap_group_mode": "all",
        "fast_roaming_enabled": False,
        "wpa_enc": "ccmp",
        "mac_filter_list": [],
        "dtim_mode": "default",
        "schedule": [],
        "bc_filter_list": "should be redacted",
        "minrate_na_data_rate_kbps": 6000,
        "mac_filter_enabled": False,
        "sae_anti_clogging": 5,
        "dtim_ng": 1,
        "x_passphrase": "should be redacted",
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
@pytest.mark.parametrize("wlan_payload", [WLAN_DATA])
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
