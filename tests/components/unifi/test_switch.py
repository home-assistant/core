"""UniFi Network switch platform tests."""

from copy import deepcopy
from datetime import timedelta
from typing import Any
from unittest.mock import patch

from aiounifi.models.message import MessageKey
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.components.unifi.const import (
    CONF_BLOCK_CLIENT,
    CONF_DPI_RESTRICTIONS,
    CONF_SITE_ID,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt as dt_util

from .conftest import (
    CONTROLLER_HOST,
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker

CLIENT_1 = {
    "hostname": "client_1",
    "ip": "10.0.0.1",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:01",
    "name": "POE Client 1",
    "oui": "Producer",
    "sw_mac": "10:00:00:00:01:01",
    "sw_port": 1,
    "wired-rx_bytes": 1234000000,
    "wired-tx_bytes": 5678000000,
}
CLIENT_2 = {
    "hostname": "client_2",
    "ip": "10.0.0.2",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:02",
    "name": "POE Client 2",
    "oui": "Producer",
    "sw_mac": "10:00:00:00:01:01",
    "sw_port": 2,
    "wired-rx_bytes": 1234000000,
    "wired-tx_bytes": 5678000000,
}
CLIENT_3 = {
    "hostname": "client_3",
    "ip": "10.0.0.3",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:03",
    "name": "Non-POE Client 3",
    "oui": "Producer",
    "sw_mac": "10:00:00:00:01:01",
    "sw_port": 3,
    "wired-rx_bytes": 1234000000,
    "wired-tx_bytes": 5678000000,
}
CLIENT_4 = {
    "hostname": "client_4",
    "ip": "10.0.0.4",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:04",
    "name": "Non-POE Client 4",
    "oui": "Producer",
    "sw_mac": "10:00:00:00:01:01",
    "sw_port": 4,
    "wired-rx_bytes": 1234000000,
    "wired-tx_bytes": 5678000000,
}
POE_SWITCH_CLIENTS = [
    {
        "hostname": "client_1",
        "ip": "10.0.0.1",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
        "name": "POE Client 1",
        "oui": "Producer",
        "sw_mac": "10:00:00:00:01:01",
        "sw_port": 1,
        "wired-rx_bytes": 1234000000,
        "wired-tx_bytes": 5678000000,
    },
    {
        "hostname": "client_2",
        "ip": "10.0.0.2",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
        "name": "POE Client 2",
        "oui": "Producer",
        "sw_mac": "10:00:00:00:01:01",
        "sw_port": 1,
        "wired-rx_bytes": 1234000000,
        "wired-tx_bytes": 5678000000,
    },
]

DEVICE_1 = {
    "board_rev": 2,
    "device_id": "mock-id",
    "ip": "10.0.1.1",
    "mac": "10:00:00:00:01:01",
    "last_seen": 1562600145,
    "model": "US16P150",
    "name": "mock-name",
    "port_overrides": [],
    "port_table": [
        {
            "media": "GE",
            "name": "Port 1",
            "port_idx": 1,
            "poe_caps": 7,
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
            "poe_caps": 7,
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
            "poe_caps": 7,
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
            "poe_caps": 7,
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

BLOCKED = {
    "blocked": True,
    "hostname": "block_client_1",
    "ip": "10.0.0.1",
    "is_guest": False,
    "is_wired": False,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:01:01",
    "name": "Block Client 1",
    "noted": True,
    "oui": "Producer",
}
UNBLOCKED = {
    "blocked": False,
    "hostname": "block_client_2",
    "ip": "10.0.0.2",
    "is_guest": False,
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:01:02",
    "name": "Block Client 2",
    "noted": True,
    "oui": "Producer",
}

EVENT_BLOCKED_CLIENT_CONNECTED = {
    "user": BLOCKED["mac"],
    "radio": "na",
    "channel": "44",
    "hostname": BLOCKED["hostname"],
    "key": "EVT_WU_Connected",
    "subsystem": "wlan",
    "site_id": "name",
    "time": 1587753456179,
    "datetime": "2020-04-24T18:37:36Z",
    "msg": f'User{[BLOCKED["mac"]]} has connected."',
    "_id": "5ea331fa30c49e00f90ddc1a",
}

EVENT_BLOCKED_CLIENT_BLOCKED = {
    "user": BLOCKED["mac"],
    "hostname": BLOCKED["hostname"],
    "key": "EVT_WC_Blocked",
    "subsystem": "wlan",
    "site_id": "name",
    "time": 1587753456179,
    "datetime": "2020-04-24T18:37:36Z",
    "msg": f'User{[BLOCKED["mac"]]} has been blocked."',
    "_id": "5ea331fa30c49e00f90ddc1a",
}

EVENT_BLOCKED_CLIENT_UNBLOCKED = {
    "user": BLOCKED["mac"],
    "hostname": BLOCKED["hostname"],
    "key": "EVT_WC_Unblocked",
    "subsystem": "wlan",
    "site_id": "name",
    "time": 1587753456179,
    "datetime": "2020-04-24T18:37:36Z",
    "msg": f'User{[BLOCKED["mac"]]} has been unblocked."',
    "_id": "5ea331fa30c49e00f90ddc1a",
}


EVENT_CLIENT_2_CONNECTED = {
    "user": CLIENT_2["mac"],
    "radio": "na",
    "channel": "44",
    "hostname": CLIENT_2["hostname"],
    "key": "EVT_WU_Connected",
    "subsystem": "wlan",
    "site_id": "name",
    "time": 1587753456179,
    "datetime": "2020-04-24T18:37:36Z",
    "msg": f'User{[CLIENT_2["mac"]]} has connected."',
    "_id": "5ea331fa30c49e00f90ddc1a",
}


DPI_GROUPS = [
    {
        "_id": "5ba29dd8e3c58f026e9d7c4a",
        "attr_no_delete": True,
        "attr_hidden_id": "Default",
        "name": "Default",
        "site_id": "name",
    },
    {
        "_id": "5f976f4ae3c58f018ec7dff6",
        "name": "Block Media Streaming",
        "site_id": "name",
        "dpiapp_ids": ["5f976f62e3c58f018ec7e17d"],
    },
]

DPI_APPS = [
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

DPI_GROUP_REMOVED_EVENT = {
    "meta": {"rc": "ok", "message": "dpigroup:delete"},
    "data": [
        {
            "_id": "5f976f4ae3c58f018ec7dff6",
            "name": "Block Media Streaming",
            "site_id": "name",
            "dpiapp_ids": [],
        }
    ],
}

DPI_GROUP_CREATED_EVENT = {
    "meta": {"rc": "ok", "message": "dpigroup:add"},
    "data": [
        {
            "name": "Block Media Streaming",
            "site_id": "name",
            "_id": "5f976f4ae3c58f018ec7dff6",
        }
    ],
}

DPI_GROUP_ADDED_APP = {
    "meta": {"rc": "ok", "message": "dpigroup:sync"},
    "data": [
        {
            "_id": "5f976f4ae3c58f018ec7dff6",
            "name": "Block Media Streaming",
            "site_id": "name",
            "dpiapp_ids": ["5f976f62e3c58f018ec7e17d"],
        }
    ],
}

DPI_GROUP_REMOVE_APP = {
    "meta": {"rc": "ok", "message": "dpigroup:sync"},
    "data": [
        {
            "_id": "5f976f4ae3c58f018ec7dff6",
            "name": "Block Media Streaming",
            "site_id": "name",
            "dpiapp_ids": [],
        }
    ],
}

DPI_APP_DISABLED_EVENT = {
    "meta": {"rc": "ok", "message": "dpiapp:sync"},
    "data": [
        {
            "_id": "5f976f62e3c58f018ec7e17d",
            "apps": [],
            "blocked": False,
            "cats": [],
            "enabled": False,
            "log": False,
            "site_id": "name",
        }
    ],
}

OUTLET_UP1 = {
    "_id": "600c8356942a6ade50707b56",
    "ip": "192.168.0.189",
    "mac": "fc:ec:da:76:4f:5f",
    "model": "UP1",
    "model_in_lts": False,
    "model_in_eol": False,
    "type": "uap",
    "version": "2.2.1.511",
    "adopted": True,
    "site_id": "545eb1f0e4b0205d14c4e548",
    "x_authkey": "345678976545678",
    "cfgversion": "4c62f1e663783447",
    "syslog_key": "41c4bcefcbc842d6eefb05b8fd9b78faa1841d10a09cebb170ce3e2f474b43b3",
    "config_network": {"type": "dhcp"},
    "setup_id": "a8730d36-8fdd-44f9-8678-1e89676f36c1",
    "x_vwirekey": "2dabb7e23b048c88b60123456789",
    "vwire_table": [],
    "dot1x_portctrl_enabled": False,
    "outlet_overrides": [{"index": 1, "name": "Outlet 1", "relay_state": True}],
    "outlet_enabled": True,
    "license_state": "registered",
    "x_aes_gcm": True,
    "inform_url": "http://192.168.0.5:8080/inform",
    "inform_ip": "192.168.0.5",
    "required_version": "2.1.3",
    "anon_id": "d2744a31-1c26-92fe-423d-6b9ba204abc7",
    "board_rev": 2,
    "manufacturer_id": 72,
    "model_incompatible": False,
    "antenna_table": [],
    "radio_table": [],
    "scan_radio_table": [],
    "ethernet_table": [],
    "port_table": [],
    "switch_caps": {},
    "has_speaker": False,
    "has_eth1": False,
    "fw_caps": 0,
    "hw_caps": 128,
    "wifi_caps": 0,
    "sys_error_caps": 0,
    "has_fan": False,
    "has_temperature": False,
    "country_code": 10752,
    "outlet_table": [
        {
            "index": 1,
            "has_relay": True,
            "has_metering": False,
            "relay_state": True,
            "name": "Outlet 1",
        },
        {
            "index": 2,
            "has_relay": False,
            "has_metering": False,
            "relay_state": False,
            "name": "Outlet 1",
        },
    ],
    "element_ap_serial": "44:d9:e7:90:f4:24",
    "connected_at": 1641678609,
    "provisioned_at": 1642054077,
    "led_override": "default",
    "led_override_color": "#0000ff",
    "led_override_color_brightness": 100,
    "outdoor_mode_override": "default",
    "lcm_brightness_override": False,
    "lcm_idle_timeout_override": False,
    "name": "Plug",
    "unsupported": False,
    "unsupported_reason": 0,
    "two_phase_adopt": False,
    "serial": "FCECDA764F5F",
    "lcm_tracker_enabled": False,
    "wlangroup_id_ng": "545eb1f0e4b0205d14c4e555",
    "supports_fingerprint_ml": False,
    "last_uplink": {
        "uplink_mac": "78:45:58:87:93:16",
        "uplink_device_name": "U6-Pro",
        "type": "wireless",
    },
    "device_id": "600c8356942a6ade50707b56",
    "uplink": {
        "uplink_mac": "78:45:58:87:93:16",
        "uplink_device_name": "U6-Pro",
        "type": "wireless",
        "up": True,
        "ap_mac": "78:45:58:87:93:16",
        "tx_rate": 54000,
        "rx_rate": 72200,
        "rssi": 60,
        "is_11ax": False,
        "is_11ac": False,
        "is_11n": True,
        "is_11b": False,
        "radio": "ng",
        "essid": "Network Name",
        "channel": 11,
        "tx_packets": 1586746,
        "rx_packets": 362176,
        "tx_bytes": 397773,
        "rx_bytes": 24423980,
        "tx_bytes-r": 0,
        "rx_bytes-r": 45,
        "uplink_source": "legacy",
    },
    "state": 1,
    "start_disconnected_millis": 1641679166349,
    "last_seen": 1642055273,
    "next_interval": 40,
    "known_cfgversion": "4c62f1e663783447",
    "start_connected_millis": 1641679166355,
    "upgradable": False,
    "adoptable_when_upgraded": False,
    "rollupgrade": False,
    "uptime": 376083,
    "_uptime": 376083,
    "locating": False,
    "connect_request_ip": "192.168.0.189",
    "connect_request_port": "49155",
    "sys_stats": {"mem_total": 98304, "mem_used": 87736},
    "system-stats": {},
    "lldp_table": [],
    "displayable_version": "2.2.1",
    "connection_network_name": "LAN",
    "startup_timestamp": 1641679190,
    "scanning": False,
    "spectrum_scanning": False,
    "meshv3_peer_mac": "",
    "element_peer_mac": "",
    "satisfaction": 100,
    "uplink_bssid": "78:45:58:87:93:17",
    "hide_ch_width": "none",
    "isolated": False,
    "radio_table_stats": [],
    "port_stats": [],
    "vap_table": [],
    "downlink_table": [],
    "vwire_vap_table": [],
    "bytes-d": 0,
    "tx_bytes-d": 0,
    "rx_bytes-d": 0,
    "bytes-r": 0,
    "element_uplink_ap_mac": "78:45:58:87:93:16",
    "prev_non_busy_state": 1,
    "stat": {
        "ap": {
            "site_id": "5a32aa4ee4b0412345678910",
            "o": "ap",
            "oid": "fc:ec:da:76:4f:5f",
            "ap": "fc:ec:da:76:4f:5f",
            "time": 1641678600000,
            "datetime": "2022-01-08T21:50:00Z",
            "user-rx_packets": 0.0,
            "guest-rx_packets": 0.0,
            "rx_packets": 0.0,
            "user-rx_bytes": 0.0,
            "guest-rx_bytes": 0.0,
            "rx_bytes": 0.0,
            "user-rx_errors": 0.0,
            "guest-rx_errors": 0.0,
            "rx_errors": 0.0,
            "user-rx_dropped": 0.0,
            "guest-rx_dropped": 0.0,
            "rx_dropped": 0.0,
            "user-rx_crypts": 0.0,
            "guest-rx_crypts": 0.0,
            "rx_crypts": 0.0,
            "user-rx_frags": 0.0,
            "guest-rx_frags": 0.0,
            "rx_frags": 0.0,
            "user-tx_packets": 0.0,
            "guest-tx_packets": 0.0,
            "tx_packets": 0.0,
            "user-tx_bytes": 0.0,
            "guest-tx_bytes": 0.0,
            "tx_bytes": 0.0,
            "user-tx_errors": 0.0,
            "guest-tx_errors": 0.0,
            "tx_errors": 0.0,
            "user-tx_dropped": 0.0,
            "guest-tx_dropped": 0.0,
            "tx_dropped": 0.0,
            "user-tx_retries": 0.0,
            "guest-tx_retries": 0.0,
            "tx_retries": 0.0,
            "user-mac_filter_rejections": 0.0,
            "guest-mac_filter_rejections": 0.0,
            "mac_filter_rejections": 0.0,
            "user-wifi_tx_attempts": 0.0,
            "guest-wifi_tx_attempts": 0.0,
            "wifi_tx_attempts": 0.0,
            "user-wifi_tx_dropped": 0.0,
            "guest-wifi_tx_dropped": 0.0,
            "wifi_tx_dropped": 0.0,
            "bytes": 0.0,
            "duration": 376663000.0,
        }
    },
    "tx_bytes": 0,
    "rx_bytes": 0,
    "bytes": 0,
    "vwireEnabled": True,
    "uplink_table": [],
    "num_sta": 0,
    "user-num_sta": 0,
    "user-wlan-num_sta": 0,
    "guest-num_sta": 0,
    "guest-wlan-num_sta": 0,
    "x_has_ssh_hostkey": False,
}


PDU_DEVICE_1 = {
    "_id": "123456654321abcdef012345",
    "required_version": "5.28.0",
    "port_table": [],
    "license_state": "registered",
    "lcm_brightness_override": False,
    "type": "usw",
    "board_rev": 4,
    "hw_caps": 136,
    "reboot_duration": 70,
    "snmp_contact": "",
    "config_network": {"type": "dhcp", "bonding_enabled": False},
    "outlet_table": [
        {
            "index": 1,
            "relay_state": True,
            "cycle_enabled": False,
            "name": "USB Outlet 1",
            "outlet_caps": 1,
        },
        {
            "index": 2,
            "relay_state": True,
            "cycle_enabled": False,
            "name": "Outlet 2",
            "outlet_caps": 3,
            "outlet_voltage": "119.644",
            "outlet_current": "0.935",
            "outlet_power": "73.827",
            "outlet_power_factor": "0.659",
        },
    ],
    "model": "USPPDUP",
    "manufacturer_id": 4,
    "ip": "192.168.1.76",
    "fw2_caps": 0,
    "jumboframe_enabled": False,
    "version": "6.5.59.14777",
    "unsupported_reason": 0,
    "adoption_completed": True,
    "outlet_enabled": True,
    "stp_version": "rstp",
    "name": "Dummy USP-PDU-Pro",
    "fw_caps": 1732968229,
    "lcm_brightness": 80,
    "internet": True,
    "mgmt_network_id": "123456654321abcdef012347",
    "gateway_mac": "01:02:03:04:05:06",
    "stp_priority": "32768",
    "lcm_night_mode_begins": "22:00",
    "two_phase_adopt": False,
    "connected_at": 1690626493,
    "inform_ip": "192.168.1.1",
    "cfgversion": "ba8f30a5a17aad64",
    "mac": "01:02:03:04:05:ff",
    "provisioned_at": 1690989511,
    "inform_url": "http://192.168.1.1:8080/inform",
    "upgrade_duration": 100,
    "ethernet_table": [{"num_port": 1, "name": "eth0", "mac": "01:02:03:04:05:a1"}],
    "flowctrl_enabled": False,
    "unsupported": False,
    "ble_caps": 0,
    "sys_error_caps": 0,
    "dot1x_portctrl_enabled": False,
    "last_uplink": {},
    "disconnected_at": 1690626452,
    "architecture": "mips",
    "x_aes_gcm": True,
    "has_fan": False,
    "outlet_overrides": [
        {
            "cycle_enabled": False,
            "name": "USB Outlet 1",
            "relay_state": True,
            "index": 1,
        },
        {"cycle_enabled": False, "name": "Outlet 2", "relay_state": True, "index": 2},
    ],
    "model_incompatible": False,
    "satisfaction": 100,
    "model_in_eol": False,
    "anomalies": -1,
    "has_temperature": False,
    "switch_caps": {},
    "adopted_by_client": "web",
    "snmp_location": "",
    "model_in_lts": False,
    "kernel_version": "4.14.115",
    "serial": "abc123",
    "power_source_ctrl_enabled": False,
    "lcm_night_mode_ends": "08:00",
    "adopted": True,
    "hash_id": "abcdef123456",
    "device_id": "mock-pdu",
    "uplink": {},
    "state": 1,
    "start_disconnected_millis": 1690626383386,
    "credential_caps": 0,
    "default": False,
    "discovered_via": "l2",
    "adopt_ip": "10.0.10.4",
    "adopt_url": "http://192.168.1.1:8080/inform",
    "last_seen": 1691518814,
    "min_inform_interval_seconds": 10,
    "upgradable": False,
    "adoptable_when_upgraded": False,
    "rollupgrade": False,
    "known_cfgversion": "abcfde03929",
    "uptime": 1193042,
    "_uptime": 1193042,
    "locating": False,
    "start_connected_millis": 1690626493324,
    "prev_non_busy_state": 5,
    "next_interval": 47,
    "sys_stats": {},
    "system-stats": {"cpu": "1.4", "mem": "28.9", "uptime": "1193042"},
    "ssh_session_table": [],
    "lldp_table": [],
    "displayable_version": "6.5.59",
    "connection_network_id": "123456654321abcdef012349",
    "connection_network_name": "Default",
    "startup_timestamp": 1690325774,
    "is_access_point": False,
    "safe_for_autoupgrade": True,
    "overheating": False,
    "power_source": "0",
    "total_max_power": 0,
    "outlet_ac_power_budget": "1875.000",
    "outlet_ac_power_consumption": "201.683",
    "downlink_table": [],
    "uplink_depth": 1,
    "downlink_lldp_macs": [],
    "dhcp_server_table": [],
    "connect_request_ip": "10.0.10.4",
    "connect_request_port": "57951",
    "ipv4_lease_expiration_timestamp_seconds": 1691576686,
    "stat": {},
    "tx_bytes": 1426780,
    "rx_bytes": 1435064,
    "bytes": 2861844,
    "num_sta": 0,
    "user-num_sta": 0,
    "guest-num_sta": 0,
    "x_has_ssh_hostkey": True,
}

WLAN = {
    "_id": "012345678910111213141516",
    "bc_filter_enabled": False,
    "bc_filter_list": [],
    "dtim_mode": "default",
    "dtim_na": 1,
    "dtim_ng": 1,
    "enabled": True,
    "group_rekey": 3600,
    "mac_filter_enabled": False,
    "mac_filter_list": [],
    "mac_filter_policy": "allow",
    "minrate_na_advertising_rates": False,
    "minrate_na_beacon_rate_kbps": 6000,
    "minrate_na_data_rate_kbps": 6000,
    "minrate_na_enabled": False,
    "minrate_na_mgmt_rate_kbps": 6000,
    "minrate_ng_advertising_rates": False,
    "minrate_ng_beacon_rate_kbps": 1000,
    "minrate_ng_data_rate_kbps": 1000,
    "minrate_ng_enabled": False,
    "minrate_ng_mgmt_rate_kbps": 1000,
    "name": "SSID 1",
    "no2ghz_oui": False,
    "schedule": [],
    "security": "wpapsk",
    "site_id": "5a32aa4ee4b0412345678910",
    "usergroup_id": "012345678910111213141518",
    "wep_idx": 1,
    "wlangroup_id": "012345678910111213141519",
    "wpa_enc": "ccmp",
    "wpa_mode": "wpa2",
    "x_iapp_key": "01234567891011121314151617181920",
    "x_passphrase": "password",
}

PORT_FORWARD_PLEX = {
    "_id": "5a32aa4ee4b0412345678911",
    "dst_port": "12345",
    "enabled": True,
    "fwd_port": "23456",
    "fwd": "10.0.0.2",
    "name": "plex",
    "pfwd_interface": "wan",
    "proto": "tcp_udp",
    "site_id": "5a32aa4ee4b0412345678910",
    "src": "any",
}

TRAFFIC_RULE = {
    "_id": "6452cd9b859d5b11aa002ea1",
    "action": "BLOCK",
    "app_category_ids": [],
    "app_ids": [],
    "bandwidth_limit": {
        "download_limit_kbps": 1024,
        "enabled": False,
        "upload_limit_kbps": 1024,
    },
    "description": "Test Traffic Rule",
    "name": "Test Traffic Rule",
    "domains": [],
    "enabled": True,
    "ip_addresses": [],
    "ip_ranges": [],
    "matching_target": "INTERNET",
    "network_ids": [],
    "regions": [],
    "schedule": {
        "date_end": "2023-05-10",
        "date_start": "2023-05-03",
        "mode": "ALWAYS",
        "repeat_on_days": [],
        "time_all_day": False,
        "time_range_end": "12:00",
        "time_range_start": "09:00",
    },
    "target_devices": [{"client_mac": CLIENT_1["mac"], "type": "CLIENT"}],
}


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_BLOCK_CLIENT: [BLOCKED["mac"]]}]
)
@pytest.mark.parametrize("client_payload", [[BLOCKED]])
@pytest.mark.parametrize("device_payload", [[DEVICE_1, OUTLET_UP1, PDU_DEVICE_1]])
@pytest.mark.parametrize("dpi_app_payload", [DPI_APPS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
@pytest.mark.parametrize("port_forward_payload", [[PORT_FORWARD_PLEX]])
@pytest.mark.parametrize(("traffic_rule_payload"), [([TRAFFIC_RULE])])
@pytest.mark.parametrize("wlan_payload", [[WLAN]])
@pytest.mark.parametrize(
    "site_payload",
    [[{"desc": "Site name", "name": "site_id", "role": "admin", "_id": "1"}]],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    site_payload: dict[str, Any],
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data with and without admin rights."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.SWITCH]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize("client_payload", [[CONTROLLER_HOST]])
@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_hub_not_client(hass: HomeAssistant) -> None:
    """Test that the cloud key doesn't become a switch."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0
    assert hass.states.get("switch.cloud_key") is None


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_BLOCK_CLIENT: [BLOCKED["mac"], UNBLOCKED["mac"]],
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        }
    ],
)
@pytest.mark.parametrize("clients_all_payload", [[BLOCKED, UNBLOCKED, CLIENT_1]])
@pytest.mark.parametrize("dpi_app_payload", [DPI_APPS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
async def test_switches(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test the update_items function with some clients."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 3

    # Block and unblock client
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/stamgr",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "mac": "00:00:00:00:01:01",
        "cmd": "block-sta",
    }

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == {
        "mac": "00:00:00:00:01:01",
        "cmd": "unblock-sta",
    }

    # Enable and disable DPI
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/dpiapp/{DPI_APPS[0]['_id']}",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.block_media_streaming"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {"enabled": False}

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.block_media_streaming"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == {"enabled": True}


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_BLOCK_CLIENT: [UNBLOCKED["mac"]]}]
)
@pytest.mark.parametrize("client_payload", [[UNBLOCKED]])
@pytest.mark.parametrize("dpi_app_payload", [DPI_APPS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
@pytest.mark.usefixtures("config_entry_setup")
async def test_remove_switches(
    hass: HomeAssistant, mock_websocket_message: WebsocketMessageMock
) -> None:
    """Test the update_items function with some clients."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    assert hass.states.get("switch.block_client_2") is not None
    assert hass.states.get("switch.block_media_streaming") is not None

    mock_websocket_message(message=MessageKey.CLIENT_REMOVED, data=[UNBLOCKED])
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    assert hass.states.get("switch.block_client_2") is None
    assert hass.states.get("switch.block_media_streaming") is not None

    mock_websocket_message(data=DPI_GROUP_REMOVED_EVENT)
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming") is None
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_BLOCK_CLIENT: [BLOCKED["mac"], UNBLOCKED["mac"]],
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        }
    ],
)
@pytest.mark.parametrize("client_payload", [[UNBLOCKED]])
@pytest.mark.parametrize("clients_all_payload", [[BLOCKED]])
async def test_block_switches(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_websocket_message: WebsocketMessageMock,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Test the update_items function with some clients."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None
    assert blocked.state == "off"

    unblocked = hass.states.get("switch.block_client_2")
    assert unblocked is not None
    assert unblocked.state == "on"

    mock_websocket_message(
        message=MessageKey.EVENT, data=EVENT_BLOCKED_CLIENT_UNBLOCKED
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None
    assert blocked.state == "on"

    mock_websocket_message(message=MessageKey.EVENT, data=EVENT_BLOCKED_CLIENT_BLOCKED)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None
    assert blocked.state == "off"

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/cmd/stamgr",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "mac": "00:00:00:00:01:01",
        "cmd": "block-sta",
    }

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == {
        "mac": "00:00:00:00:01:01",
        "cmd": "unblock-sta",
    }


@pytest.mark.parametrize("dpi_app_payload", [DPI_APPS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
@pytest.mark.usefixtures("config_entry_setup")
async def test_dpi_switches(
    hass: HomeAssistant, mock_websocket_message: WebsocketMessageMock
) -> None:
    """Test the update_items function with some clients."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    assert hass.states.get("switch.block_media_streaming").state == STATE_ON

    mock_websocket_message(data=DPI_APP_DISABLED_EVENT)
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming").state == STATE_OFF

    # Remove app
    mock_websocket_message(data=DPI_GROUP_REMOVE_APP)
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming") is None
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


@pytest.mark.parametrize("dpi_app_payload", [DPI_APPS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
@pytest.mark.usefixtures("config_entry_setup")
async def test_dpi_switches_add_second_app(
    hass: HomeAssistant, mock_websocket_message: WebsocketMessageMock
) -> None:
    """Test the update_items function with some clients."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1
    assert hass.states.get("switch.block_media_streaming").state == STATE_ON

    second_app_event = {
        "apps": [524292],
        "blocked": False,
        "cats": [],
        "enabled": False,
        "log": False,
        "site_id": "name",
        "_id": "61783e89c1773a18c0c61f00",
    }
    mock_websocket_message(message=MessageKey.DPI_APP_ADDED, data=second_app_event)
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming").state == STATE_ON

    add_second_app_to_group = {
        "_id": "5f976f4ae3c58f018ec7dff6",
        "name": "Block Media Streaming",
        "site_id": "name",
        "dpiapp_ids": ["5f976f62e3c58f018ec7e17d", "61783e89c1773a18c0c61f00"],
    }
    mock_websocket_message(
        message=MessageKey.DPI_GROUP_UPDATED, data=add_second_app_to_group
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming").state == STATE_OFF

    second_app_event_enabled = {
        "apps": [524292],
        "blocked": False,
        "cats": [],
        "enabled": True,
        "log": False,
        "site_id": "name",
        "_id": "61783e89c1773a18c0c61f00",
    }
    mock_websocket_message(
        message=MessageKey.DPI_APP_UPDATED, data=second_app_event_enabled
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming").state == STATE_ON


@pytest.mark.parametrize(("traffic_rule_payload"), [([TRAFFIC_RULE])])
async def test_traffic_rules(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    traffic_rule_payload: list[dict[str, Any]],
) -> None:
    """Test control of UniFi traffic rules."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Validate state object
    assert hass.states.get("switch.unifi_network_test_traffic_rule").state == STATE_ON

    traffic_rule = deepcopy(traffic_rule_payload[0])

    # Disable traffic rule
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/v2/api/site/{config_entry_setup.data[CONF_SITE_ID]}"
        f"/trafficrules/{traffic_rule['_id']}",
    )

    call_count = aioclient_mock.call_count

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.unifi_network_test_traffic_rule"},
        blocking=True,
    )
    # Updating the value for traffic rules will make another call to retrieve the values
    assert aioclient_mock.call_count == call_count + 2
    expected_disable_call = deepcopy(traffic_rule)
    expected_disable_call["enabled"] = False

    assert aioclient_mock.mock_calls[call_count][2] == expected_disable_call

    call_count = aioclient_mock.call_count

    # Enable traffic rule
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.unifi_network_test_traffic_rule"},
        blocking=True,
    )

    expected_enable_call = deepcopy(traffic_rule)
    expected_enable_call["enabled"] = True

    assert aioclient_mock.call_count == call_count + 2
    assert aioclient_mock.mock_calls[call_count][2] == expected_enable_call


@pytest.mark.parametrize(
    ("device_payload", "entity_id", "outlet_index", "expected_switches"),
    [
        ([OUTLET_UP1], "plug_outlet_1", 1, 1),
        ([PDU_DEVICE_1], "dummy_usp_pdu_pro_usb_outlet_1", 1, 2),
        ([PDU_DEVICE_1], "dummy_usp_pdu_pro_outlet_2", 2, 2),
    ],
)
async def test_outlet_switches(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_websocket_message: WebsocketMessageMock,
    config_entry_setup: MockConfigEntry,
    device_payload: list[dict[str, Any]],
    entity_id: str,
    outlet_index: int,
    expected_switches: int,
) -> None:
    """Test the outlet entities."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == expected_switches

    # Validate state object
    assert hass.states.get(f"switch.{entity_id}").state == STATE_ON

    # Update state object
    device_1 = deepcopy(device_payload[0])
    device_1["outlet_table"][outlet_index - 1]["relay_state"] = False
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.{entity_id}").state == STATE_OFF

    # Turn off outlet
    device_id = device_payload[0]["device_id"]
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/device/{device_id}",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: f"switch.{entity_id}"},
        blocking=True,
    )

    expected_off_overrides = deepcopy(device_1["outlet_overrides"])
    expected_off_overrides[outlet_index - 1]["relay_state"] = False

    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "outlet_overrides": expected_off_overrides
    }

    # Turn on outlet
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: f"switch.{entity_id}"},
        blocking=True,
    )

    expected_on_overrides = deepcopy(device_1["outlet_overrides"])
    expected_on_overrides[outlet_index - 1]["relay_state"] = True
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == {
        "outlet_overrides": expected_on_overrides
    }

    # Device gets disabled
    device_1["disabled"] = True
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.{entity_id}").state == STATE_UNAVAILABLE

    # Device gets re-enabled
    device_1["disabled"] = False
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get(f"switch.{entity_id}").state == STATE_OFF


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_BLOCK_CLIENT: [BLOCKED["mac"]],
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_DPI_RESTRICTIONS: False,
        }
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_new_client_discovered_on_block_control(
    hass: HomeAssistant, mock_websocket_message: WebsocketMessageMock
) -> None:
    """Test if 2nd update has a new client."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0
    assert hass.states.get("switch.block_client_1") is None

    mock_websocket_message(message=MessageKey.CLIENT, data=BLOCKED)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1
    assert hass.states.get("switch.block_client_1") is not None


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_BLOCK_CLIENT: [BLOCKED["mac"]]}]
)
@pytest.mark.parametrize("clients_all_payload", [[BLOCKED, UNBLOCKED]])
async def test_option_block_clients(
    hass: HomeAssistant,
    config_entry_setup: MockConfigEntry,
    clients_all_payload: list[dict[str, Any]],
) -> None:
    """Test the changes to option reflects accordingly."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Add a second switch
    hass.config_entries.async_update_entry(
        config_entry_setup,
        options={
            CONF_BLOCK_CLIENT: [
                clients_all_payload[0]["mac"],
                clients_all_payload[1]["mac"],
            ]
        },
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Remove the second switch again
    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_BLOCK_CLIENT: [clients_all_payload[0]["mac"]]}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Enable one and remove the other one
    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_BLOCK_CLIENT: [clients_all_payload[1]["mac"]]}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0

    # Remove one
    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_BLOCK_CLIENT: []}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


@pytest.mark.parametrize(
    "config_entry_options",
    [{CONF_TRACK_CLIENTS: False, CONF_TRACK_DEVICES: False}],
)
@pytest.mark.parametrize("client_payload", [[CLIENT_1]])
@pytest.mark.parametrize("dpi_app_payload", [DPI_APPS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
async def test_option_remove_switches(
    hass: HomeAssistant, config_entry_setup: MockConfigEntry
) -> None:
    """Test removal of DPI switch when options updated."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Disable DPI Switches
    hass.config_entries.async_update_entry(
        config_entry_setup, options={CONF_DPI_RESTRICTIONS: False}
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
async def test_poe_port_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Test PoE port entities work."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0

    ent_reg_entry = entity_registry.async_get("switch.mock_name_port_1_poe")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(
        entity_id="switch.mock_name_port_1_poe", disabled_by=None
    )
    entity_registry.async_update_entity(
        entity_id="switch.mock_name_port_2_poe", disabled_by=None
    )

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Validate state object
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_ON

    # Update state object
    device_1 = deepcopy(device_payload[0])
    device_1["port_table"][0]["poe_mode"] = "off"
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_OFF

    # Turn off PoE
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/device/mock-id",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.mock_name_port_1_poe"},
        blocking=True,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "port_overrides": [{"poe_mode": "off", "port_idx": 1, "portconf_id": "1a1"}]
    }

    # Turn on PoE
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.mock_name_port_1_poe"},
        blocking=True,
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.mock_name_port_2_poe"},
        blocking=True,
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == {
        "port_overrides": [
            {"poe_mode": "auto", "port_idx": 1, "portconf_id": "1a1"},
            {"poe_mode": "off", "port_idx": 2, "portconf_id": "1a2"},
        ]
    }

    # Device gets disabled
    device_1["disabled"] = True
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_UNAVAILABLE

    # Device gets re-enabled
    device_1["disabled"] = False
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_OFF


@pytest.mark.parametrize("wlan_payload", [[WLAN]])
async def test_wlan_switches(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_message: WebsocketMessageMock,
    wlan_payload: list[dict[str, Any]],
) -> None:
    """Test control of UniFi WLAN availability."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Validate state object
    assert hass.states.get("switch.ssid_1").state == STATE_ON

    # Update state object
    wlan = deepcopy(wlan_payload[0])
    wlan["enabled"] = False
    mock_websocket_message(message=MessageKey.WLAN_CONF_UPDATED, data=wlan)
    await hass.async_block_till_done()
    assert hass.states.get("switch.ssid_1").state == STATE_OFF

    # Disable WLAN
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/wlanconf/{wlan['_id']}",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.ssid_1"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {"enabled": False}

    # Enable WLAN
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.ssid_1"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == {"enabled": True}


@pytest.mark.parametrize("port_forward_payload", [[PORT_FORWARD_PLEX]])
async def test_port_forwarding_switches(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: MockConfigEntry,
    mock_websocket_message: WebsocketMessageMock,
    port_forward_payload: list[dict[str, Any]],
) -> None:
    """Test control of UniFi port forwarding."""
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Validate state object
    assert hass.states.get("switch.unifi_network_plex").state == STATE_ON

    # Update state object
    data = port_forward_payload[0].copy()
    data["enabled"] = False
    mock_websocket_message(message=MessageKey.PORT_FORWARD_UPDATED, data=data)
    await hass.async_block_till_done()
    assert hass.states.get("switch.unifi_network_plex").state == STATE_OFF

    # Disable port forward
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{config_entry_setup.data[CONF_HOST]}:1234"
        f"/api/s/{config_entry_setup.data[CONF_SITE_ID]}/rest/portforward/{data['_id']}",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.unifi_network_plex"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    data = port_forward_payload[0].copy()
    data["enabled"] = False
    assert aioclient_mock.mock_calls[0][2] == data

    # Enable port forward
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.unifi_network_plex"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == port_forward_payload[0]

    # Remove entity on deleted message
    mock_websocket_message(
        message=MessageKey.PORT_FORWARD_DELETED, data=port_forward_payload[0]
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            OUTLET_UP1,
            {
                "board_rev": 3,
                "device_id": "mock-id",
                "ip": "10.0.0.1",
                "last_seen": 1562600145,
                "mac": "00:00:00:00:01:01",
                "model": "US16P150",
                "name": "switch",
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
                "port_table": [
                    {
                        "media": "GE",
                        "name": "Port 1",
                        "port_idx": 1,
                        "poe_caps": 7,
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
            },
        ]
    ],
)
async def test_updating_unique_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    config_entry: MockConfigEntry,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify outlet control and poe control unique ID update works."""
    entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        UNIFI_DOMAIN,
        f"{device_payload[0]['mac']}-outlet-1",
        suggested_object_id="plug_outlet_1",
        config_entry=config_entry,
    )
    entity_registry.async_get_or_create(
        SWITCH_DOMAIN,
        UNIFI_DOMAIN,
        f"{device_payload[1]['mac']}-poe-1",
        suggested_object_id="switch_port_1_poe",
        config_entry=config_entry,
    )

    await config_entry_factory()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    assert hass.states.get("switch.plug_outlet_1")
    assert hass.states.get("switch.switch_port_1_poe")


@pytest.mark.parametrize(
    "config_entry_options", [{CONF_BLOCK_CLIENT: [UNBLOCKED["mac"]]}]
)
@pytest.mark.parametrize("client_payload", [[UNBLOCKED]])
@pytest.mark.parametrize("device_payload", [[DEVICE_1, OUTLET_UP1]])
@pytest.mark.parametrize("dpi_app_payload", [DPI_APPS])
@pytest.mark.parametrize("dpi_group_payload", [DPI_GROUPS])
@pytest.mark.parametrize("port_forward_payload", [[PORT_FORWARD_PLEX]])
@pytest.mark.parametrize(("traffic_rule_payload"), [([TRAFFIC_RULE])])
@pytest.mark.parametrize("wlan_payload", [[WLAN]])
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hub_state_change(
    hass: HomeAssistant, mock_websocket_state: WebsocketStateManager
) -> None:
    """Verify entities state reflect on hub connection becoming unavailable."""
    entity_ids = (
        "switch.block_client_2",
        "switch.mock_name_port_1_poe",
        "switch.plug_outlet_1",
        "switch.block_media_streaming",
        "switch.unifi_network_plex",
        "switch.unifi_network_test_traffic_rule",
        "switch.ssid_1",
    )
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_ON

    # Controller disconnects
    await mock_websocket_state.disconnect()
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Controller reconnects
    await mock_websocket_state.reconnect()
    for entity_id in entity_ids:
        assert hass.states.get(entity_id).state == STATE_ON
