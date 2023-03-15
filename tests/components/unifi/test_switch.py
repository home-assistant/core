"""UniFi Network switch platform tests."""
from copy import deepcopy
from datetime import timedelta

from aiounifi.models.message import MessageKey
from aiounifi.websocket import WebsocketState

from homeassistant import config_entries
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SwitchDeviceClass,
)
from homeassistant.components.unifi.const import (
    CONF_BLOCK_CLIENT,
    CONF_DPI_RESTRICTIONS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from homeassistant.util import dt

from .test_controller import (
    CONTROLLER_HOST,
    DESCRIPTION,
    ENTRY_CONFIG,
    setup_unifi_integration,
)

from tests.common import async_fire_time_changed
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
    "outlet_overrides": [],
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


async def test_no_clients(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the update_clients function when no clients are found."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_DPI_RESTRICTIONS: False,
        },
    )

    assert aioclient_mock.call_count == 10
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_controller_not_client(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the controller doesn't become a switch."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_TRACK_CLIENTS: False, CONF_TRACK_DEVICES: False},
        clients_response=[CONTROLLER_HOST],
        devices_response=[DEVICE_1],
    )

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0
    cloudkey = hass.states.get("switch.cloud_key")
    assert cloudkey is None


async def test_not_admin(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that switch platform only work on an admin account."""
    description = deepcopy(DESCRIPTION)
    description[0]["site_role"] = "not admin"
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_TRACK_CLIENTS: False, CONF_TRACK_DEVICES: False},
        site_description=description,
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the update_items function with some clients."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_BLOCK_CLIENT: [BLOCKED["mac"], UNBLOCKED["mac"]],
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        },
        clients_response=[CLIENT_4],
        clients_all_response=[BLOCKED, UNBLOCKED, CLIENT_1],
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=DPI_APPS,
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 3

    switch_4 = hass.states.get("switch.poe_client_4")
    assert switch_4 is None

    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None
    assert blocked.state == "off"

    unblocked = hass.states.get("switch.block_client_2")
    assert unblocked is not None
    assert unblocked.state == "on"

    dpi_switch = hass.states.get("switch.block_media_streaming")
    assert dpi_switch is not None
    assert dpi_switch.state == "on"
    assert dpi_switch.attributes["icon"] == "mdi:network"

    ent_reg = er.async_get(hass)
    for entry_id in ("switch.block_client_1", "switch.block_media_streaming"):
        assert ent_reg.async_get(entry_id).entity_category is EntityCategory.CONFIG

    # Block and unblock client

    aioclient_mock.post(
        f"https://{controller.host}:1234/api/s/{controller.site}/cmd/stamgr",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 11
    assert aioclient_mock.mock_calls[10][2] == {
        "mac": "00:00:00:00:01:01",
        "cmd": "block-sta",
    }

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 12
    assert aioclient_mock.mock_calls[11][2] == {
        "mac": "00:00:00:00:01:01",
        "cmd": "unblock-sta",
    }

    # Enable and disable DPI

    aioclient_mock.put(
        f"https://{controller.host}:1234/api/s/{controller.site}/rest/dpiapp/5f976f62e3c58f018ec7e17d",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.block_media_streaming"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 13
    assert aioclient_mock.mock_calls[12][2] == {"enabled": False}

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on",
        {"entity_id": "switch.block_media_streaming"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 14
    assert aioclient_mock.mock_calls[13][2] == {"enabled": True}

    # Make sure no duplicates arise on generic signal update
    async_dispatcher_send(hass, controller.signal_update)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 3


async def test_remove_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test the update_items function with some clients."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_BLOCK_CLIENT: [UNBLOCKED["mac"]]},
        clients_response=[UNBLOCKED],
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=DPI_APPS,
    )

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    assert hass.states.get("switch.block_client_2") is not None
    assert hass.states.get("switch.block_media_streaming") is not None

    mock_unifi_websocket(message=MessageKey.CLIENT_REMOVED, data=[UNBLOCKED])
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    assert hass.states.get("switch.block_client_2") is None
    assert hass.states.get("switch.block_media_streaming") is not None

    mock_unifi_websocket(data=DPI_GROUP_REMOVED_EVENT)
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming") is None
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_block_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test the update_items function with some clients."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_BLOCK_CLIENT: [BLOCKED["mac"], UNBLOCKED["mac"]],
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        },
        clients_response=[UNBLOCKED],
        clients_all_response=[BLOCKED],
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None
    assert blocked.state == "off"

    unblocked = hass.states.get("switch.block_client_2")
    assert unblocked is not None
    assert unblocked.state == "on"

    mock_unifi_websocket(message=MessageKey.EVENT, data=EVENT_BLOCKED_CLIENT_UNBLOCKED)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None
    assert blocked.state == "on"

    mock_unifi_websocket(message=MessageKey.EVENT, data=EVENT_BLOCKED_CLIENT_BLOCKED)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None
    assert blocked.state == "off"

    aioclient_mock.post(
        f"https://{controller.host}:1234/api/s/{controller.site}/cmd/stamgr",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 11
    assert aioclient_mock.mock_calls[10][2] == {
        "mac": "00:00:00:00:01:01",
        "cmd": "block-sta",
    }

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 12
    assert aioclient_mock.mock_calls[11][2] == {
        "mac": "00:00:00:00:01:01",
        "cmd": "unblock-sta",
    }


async def test_dpi_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test the update_items function with some clients."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=DPI_APPS,
    )

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    dpi_switch = hass.states.get("switch.block_media_streaming")
    assert dpi_switch is not None
    assert dpi_switch.state == STATE_ON
    assert dpi_switch.attributes["icon"] == "mdi:network"

    mock_unifi_websocket(data=DPI_APP_DISABLED_EVENT)
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming").state == STATE_OFF

    # Availability signalling

    # Controller disconnects
    mock_unifi_websocket(state=WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get("switch.block_media_streaming").state == STATE_UNAVAILABLE

    # Controller reconnects
    mock_unifi_websocket(state=WebsocketState.RUNNING)
    await hass.async_block_till_done()
    assert hass.states.get("switch.block_media_streaming").state == STATE_OFF

    # Remove app
    mock_unifi_websocket(data=DPI_GROUP_REMOVE_APP)
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming") is None
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_dpi_switches_add_second_app(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test the update_items function with some clients."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=DPI_APPS,
    )

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
    mock_unifi_websocket(message=MessageKey.DPI_APP_ADDED, data=second_app_event)
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming").state == STATE_ON

    add_second_app_to_group = {
        "_id": "5f976f4ae3c58f018ec7dff6",
        "name": "Block Media Streaming",
        "site_id": "name",
        "dpiapp_ids": ["5f976f62e3c58f018ec7e17d", "61783e89c1773a18c0c61f00"],
    }
    mock_unifi_websocket(
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
    mock_unifi_websocket(
        message=MessageKey.DPI_APP_UPDATED, data=second_app_event_enabled
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.block_media_streaming").state == STATE_ON


async def test_outlet_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test the outlet entities."""
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, devices_response=[OUTLET_UP1]
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Validate state object
    switch_1 = hass.states.get("switch.plug_outlet_1")
    assert switch_1 is not None
    assert switch_1.state == STATE_ON
    assert switch_1.attributes.get(ATTR_DEVICE_CLASS) == SwitchDeviceClass.OUTLET

    # Update state object
    device_1 = deepcopy(OUTLET_UP1)
    device_1["outlet_table"][0]["relay_state"] = False
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.plug_outlet_1").state == STATE_OFF

    # Turn off outlet
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{controller.host}:1234/api/s/{controller.site}/rest/device/600c8356942a6ade50707b56",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.plug_outlet_1"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1
    assert aioclient_mock.mock_calls[0][2] == {
        "outlet_overrides": [{"index": 1, "name": "Outlet 1", "relay_state": False}]
    }

    # Turn on outlet
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.plug_outlet_1"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == {
        "outlet_overrides": [{"index": 1, "name": "Outlet 1", "relay_state": True}]
    }

    # Availability signalling

    # Controller disconnects
    mock_unifi_websocket(state=WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get("switch.plug_outlet_1").state == STATE_UNAVAILABLE

    # Controller reconnects
    mock_unifi_websocket(state=WebsocketState.RUNNING)
    await hass.async_block_till_done()
    assert hass.states.get("switch.plug_outlet_1").state == STATE_OFF

    # Device gets disabled
    device_1["disabled"] = True
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.plug_outlet_1").state == STATE_UNAVAILABLE

    # Device gets re-enabled
    device_1["disabled"] = False
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.plug_outlet_1").state == STATE_OFF

    # Unload config entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    assert hass.states.get("switch.plug_outlet_1").state == STATE_UNAVAILABLE

    # Remove config entry
    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("switch.plug_outlet_1") is None


async def test_new_client_discovered_on_block_control(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test if 2nd update has a new client."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_BLOCK_CLIENT: [BLOCKED["mac"]],
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
            CONF_DPI_RESTRICTIONS: False,
        },
    )

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0
    assert hass.states.get("switch.block_client_1") is None

    mock_unifi_websocket(message=MessageKey.CLIENT, data=BLOCKED)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1
    assert hass.states.get("switch.block_client_1") is not None


async def test_option_block_clients(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the changes to option reflects accordingly."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_BLOCK_CLIENT: [BLOCKED["mac"]]},
        clients_all_response=[BLOCKED, UNBLOCKED],
    )
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Add a second switch
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_BLOCK_CLIENT: [BLOCKED["mac"], UNBLOCKED["mac"]]},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Remove the second switch again
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_BLOCK_CLIENT: [BLOCKED["mac"]]},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Enable one and remove another one
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_BLOCK_CLIENT: [UNBLOCKED["mac"]]},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0

    # Remove one
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_BLOCK_CLIENT: []},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_option_remove_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test removal of DPI switch when options updated."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        },
        clients_response=[CLIENT_1],
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=DPI_APPS,
    )
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    # Disable DPI Switches
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_DPI_RESTRICTIONS: False},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_poe_port_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test the update_items function with some clients."""
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, devices_response=[DEVICE_1]
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0

    ent_reg = er.async_get(hass)
    ent_reg_entry = ent_reg.async_get("switch.mock_name_port_1_poe")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert ent_reg_entry.entity_category is EntityCategory.CONFIG

    # Enable entity
    ent_reg.async_update_entity(
        entity_id="switch.mock_name_port_1_poe", disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Validate state object
    switch_1 = hass.states.get("switch.mock_name_port_1_poe")
    assert switch_1 is not None
    assert switch_1.state == STATE_ON
    assert switch_1.attributes.get(ATTR_DEVICE_CLASS) == SwitchDeviceClass.OUTLET

    # Update state object
    device_1 = deepcopy(DEVICE_1)
    device_1["port_table"][0]["poe_mode"] = "off"
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_OFF

    # Turn off PoE
    aioclient_mock.clear_requests()
    aioclient_mock.put(
        f"https://{controller.host}:1234/api/s/{controller.site}/rest/device/mock-id",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_off",
        {"entity_id": "switch.mock_name_port_1_poe"},
        blocking=True,
    )
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
    assert aioclient_mock.call_count == 2
    assert aioclient_mock.mock_calls[1][2] == {
        "port_overrides": [{"poe_mode": "auto", "port_idx": 1, "portconf_id": "1a1"}]
    }

    # Availability signalling

    # Controller disconnects
    mock_unifi_websocket(state=WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_UNAVAILABLE

    # Controller reconnects
    mock_unifi_websocket(state=WebsocketState.RUNNING)
    await hass.async_block_till_done()
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_OFF

    # Device gets disabled
    device_1["disabled"] = True
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_UNAVAILABLE

    # Device gets re-enabled
    device_1["disabled"] = False
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("switch.mock_name_port_1_poe").state == STATE_OFF


async def test_remove_poe_client_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test old PoE client switches are removed."""

    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=UNIFI_DOMAIN,
        title="Mock Title",
        data=ENTRY_CONFIG,
        source="test",
        options={},
        entry_id="1",
    )

    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        SWITCH_DOMAIN,
        UNIFI_DOMAIN,
        "poe-123",
        config_entry=config_entry,
    )

    await setup_unifi_integration(hass, aioclient_mock)

    assert not [
        entry
        for entry in ent_reg.entities.values()
        if entry.config_entry_id == config_entry.entry_id
    ]
