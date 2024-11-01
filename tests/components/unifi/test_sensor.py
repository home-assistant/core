"""UniFi Network sensor platform tests."""

from copy import deepcopy
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from aiounifi.models.device import DeviceState
from aiounifi.models.message import MessageKey
from freezegun.api import FrozenDateTimeFactory, freeze_time
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SCAN_INTERVAL,
    SensorDeviceClass,
)
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_DETECTION_TIME,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DEFAULT_DETECTION_TIME,
    DEVICE_STATES,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
import homeassistant.util.dt as dt_util

from .conftest import (
    ConfigEntryFactoryType,
    WebsocketMessageMock,
    WebsocketStateManager,
)

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

WIRED_CLIENT = {
    "hostname": "Wired client",
    "is_wired": True,
    "mac": "00:00:00:00:00:01",
    "oui": "Producer",
    "wired-rx_bytes-r": 1234000000,
    "wired-tx_bytes-r": 5678000000,
    "uptime": 1600094505,
}
WIRELESS_CLIENT = {
    "is_wired": False,
    "mac": "00:00:00:00:00:02",
    "name": "Wireless client",
    "oui": "Producer",
    "rx_bytes-r": 2345000000.0,
    "tx_bytes-r": 6789000000.0,
    "uptime": 60,
}

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

PDU_OUTLETS_UPDATE_DATA = [
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
        "outlet_power": "123.45",
        "outlet_power_factor": "0.659",
    },
]


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
        }
    ],
)
@pytest.mark.parametrize("client_payload", [[WIRED_CLIENT, WIRELESS_CLIENT]])
@pytest.mark.parametrize(
    "device_payload",
    [
        [
            DEVICE_1,
            PDU_DEVICE_1,
            {  # Temperature
                "board_rev": 3,
                "device_id": "mock-id",
                "general_temperature": 30,
                "has_fan": True,
                "has_temperature": True,
                "fan_level": 0,
                "ip": "10.0.1.1",
                "last_seen": 1562600145,
                "mac": "20:00:00:00:01:01",
                "model": "US16P150",
                "name": "Device",
                "next_interval": 20,
                "overheating": True,
                "state": 1,
                "type": "usw",
                "upgradable": True,
                "uptime": 60,
                "version": "4.0.42.10433",
            },
            {  # Latency monitors
                "board_rev": 2,
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": "10:00:00:00:01:01",
                "last_seen": 1562600145,
                "model": "US16P150",
                "name": "mock-name",
                "port_overrides": [],
                "uptime_stats": {
                    "WAN": {
                        "availability": 100.0,
                        "latency_average": 39,
                        "monitors": [
                            {
                                "availability": 100.0,
                                "latency_average": 56,
                                "target": "www.microsoft.com",
                                "type": "icmp",
                            },
                            {
                                "availability": 100.0,
                                "latency_average": 53,
                                "target": "google.com",
                                "type": "icmp",
                            },
                            {
                                "availability": 100.0,
                                "latency_average": 30,
                                "target": "1.1.1.1",
                                "type": "icmp",
                            },
                        ],
                    },
                    "WAN2": {
                        "monitors": [
                            {
                                "availability": 0.0,
                                "target": "www.microsoft.com",
                                "type": "icmp",
                            },
                            {
                                "availability": 0.0,
                                "target": "google.com",
                                "type": "icmp",
                            },
                            {"availability": 0.0, "target": "1.1.1.1", "type": "icmp"},
                        ],
                    },
                },
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
            },
        ]
    ],
)
@pytest.mark.parametrize("wlan_payload", [[WLAN]])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2021-01-01 01:01:00")
async def test_entity_and_device_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory,
    snapshot: SnapshotAssertion,
) -> None:
    """Validate entity and device data."""
    with patch("homeassistant.components.unifi.PLATFORMS", [Platform.SENSOR]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "config_entry_options",
    [{CONF_ALLOW_BANDWIDTH_SENSORS: True, CONF_ALLOW_UPTIME_SENSORS: True}],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_no_clients(hass: HomeAssistant) -> None:
    """Test the update_clients function when no clients are found."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: False,
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        }
    ],
)
@pytest.mark.parametrize("client_payload", [[WIRED_CLIENT, WIRELESS_CLIENT]])
async def test_bandwidth_sensors(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
    config_entry_options: MappingProxyType[str, Any],
    config_entry_setup: MockConfigEntry,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify that bandwidth sensors are working as expected."""
    # Verify state update
    wireless_client = deepcopy(client_payload[1])
    wireless_client["rx_bytes-r"] = 3456000000
    wireless_client["tx_bytes-r"] = 7891000000

    mock_websocket_message(message=MessageKey.CLIENT, data=wireless_client)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wireless_client_rx").state == "3456.0"
    assert hass.states.get("sensor.wireless_client_tx").state == "7891.0"

    # Verify reset sensor after heartbeat expires

    new_time = dt_util.utcnow()
    wireless_client["last_seen"] = dt_util.as_timestamp(new_time)

    mock_websocket_message(message=MessageKey.CLIENT, data=wireless_client)
    await hass.async_block_till_done()

    with freeze_time(new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.wireless_client_rx").state == "3456.0"
    assert hass.states.get("sensor.wireless_client_tx").state == "7891.0"

    new_time += timedelta(
        seconds=(
            config_entry_setup.options.get(CONF_DETECTION_TIME, DEFAULT_DETECTION_TIME)
            + 1
        )
    )
    with freeze_time(new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.wireless_client_rx").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.wireless_client_tx").state == STATE_UNAVAILABLE

    # Disable option
    options = deepcopy(config_entry_options)
    options[CONF_ALLOW_BANDWIDTH_SENSORS] = False
    hass.config_entries.async_update_entry(config_entry_setup, options=options)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    assert hass.states.get("sensor.wireless_client_rx") is None
    assert hass.states.get("sensor.wireless_client_tx") is None
    assert hass.states.get("sensor.wired_client_rx") is None
    assert hass.states.get("sensor.wired_client_tx") is None

    # Enable option
    options = deepcopy(config_entry_options)
    options[CONF_ALLOW_BANDWIDTH_SENSORS] = True
    hass.config_entries.async_update_entry(config_entry_setup, options=options)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    assert hass.states.get("sensor.wireless_client_rx")
    assert hass.states.get("sensor.wireless_client_tx")
    assert hass.states.get("sensor.wired_client_rx")
    assert hass.states.get("sensor.wired_client_tx")


@pytest.mark.parametrize(
    "config_entry_options",
    [{CONF_ALLOW_BANDWIDTH_SENSORS: True, CONF_ALLOW_UPTIME_SENSORS: True}],
)
@pytest.mark.parametrize("client_payload", [[WIRED_CLIENT, WIRELESS_CLIENT]])
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_remove_sensors(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify removing of clients work as expected."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6
    assert hass.states.get("sensor.wired_client_rx")
    assert hass.states.get("sensor.wired_client_tx")
    assert hass.states.get("sensor.wired_client_uptime")
    assert hass.states.get("sensor.wireless_client_rx")
    assert hass.states.get("sensor.wireless_client_tx")
    assert hass.states.get("sensor.wireless_client_uptime")

    # Remove wired client
    mock_websocket_message(message=MessageKey.CLIENT_REMOVED, data=client_payload[0])
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3
    assert hass.states.get("sensor.wired_client_rx") is None
    assert hass.states.get("sensor.wired_client_tx") is None
    assert hass.states.get("sensor.wired_client_uptime") is None
    assert hass.states.get("sensor.wireless_client_rx")
    assert hass.states.get("sensor.wireless_client_tx")
    assert hass.states.get("sensor.wireless_client_uptime")


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_poe_port_switches(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    mock_websocket_state: WebsocketStateManager,
) -> None:
    """Test the update_items function with some clients."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    ent_reg_entry = entity_registry.async_get("sensor.mock_name_port_1_poe_power")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(
        entity_id="sensor.mock_name_port_1_poe_power", disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Validate state object
    poe_sensor = hass.states.get("sensor.mock_name_port_1_poe_power")
    assert poe_sensor.state == "2.56"
    assert poe_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER

    # Update state object
    device_1 = deepcopy(DEVICE_1)
    device_1["port_table"][0]["poe_power"] = "5.12"
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mock_name_port_1_poe_power").state == "5.12"

    # PoE is disabled
    device_1 = deepcopy(DEVICE_1)
    device_1["port_table"][0]["poe_mode"] = "off"
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mock_name_port_1_poe_power").state == "0"

    # Availability signalling

    # Controller disconnects
    await mock_websocket_state.disconnect()
    assert (
        hass.states.get("sensor.mock_name_port_1_poe_power").state == STATE_UNAVAILABLE
    )

    # Controller reconnects
    await mock_websocket_state.reconnect()
    assert (
        hass.states.get("sensor.mock_name_port_1_poe_power").state != STATE_UNAVAILABLE
    )

    # Device gets disabled
    device_1["disabled"] = True
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.mock_name_port_1_poe_power").state == STATE_UNAVAILABLE
    )

    # Device gets re-enabled
    device_1["disabled"] = False
    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mock_name_port_1_poe_power")


@pytest.mark.parametrize("wlan_payload", [[WLAN]])
async def test_wlan_client_sensors(
    hass: HomeAssistant,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    mock_websocket_state: WebsocketStateManager,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify that WLAN client sensors are working as expected."""
    client_payload += [
        {
            "essid": "SSID 1",
            "is_wired": False,
            "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
            "mac": "00:00:00:00:00:01",
            "name": "Wireless client",
            "oui": "Producer",
            "rx_bytes-r": 2345000000,
            "tx_bytes-r": 6789000000,
        },
        {
            "essid": "SSID 2",
            "is_wired": False,
            "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
            "mac": "00:00:00:00:00:02",
            "name": "Wireless client2",
            "oui": "Producer2",
            "rx_bytes-r": 2345000000,
            "tx_bytes-r": 6789000000,
        },
    ]
    await config_entry_factory()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1

    # Validate state object
    assert hass.states.get("sensor.ssid_1").state == "1"

    # Verify state update - increasing number
    wireless_client_1 = client_payload[0]
    wireless_client_1["essid"] = "SSID 1"
    mock_websocket_message(message=MessageKey.CLIENT, data=wireless_client_1)
    wireless_client_2 = client_payload[1]
    wireless_client_2["essid"] = "SSID 1"
    mock_websocket_message(message=MessageKey.CLIENT, data=wireless_client_2)
    await hass.async_block_till_done()

    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1.state == "1"

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1.state == "2"

    # Verify state update - decreasing number

    wireless_client_1["essid"] = "SSID"
    mock_websocket_message(message=MessageKey.CLIENT, data=wireless_client_1)

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1.state == "1"

    # Verify state update - decreasing number

    wireless_client_2["last_seen"] = 0
    mock_websocket_message(message=MessageKey.CLIENT, data=wireless_client_2)

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1.state == "0"

    # Availability signalling

    # Controller disconnects
    await mock_websocket_state.disconnect()
    assert hass.states.get("sensor.ssid_1").state == STATE_UNAVAILABLE

    # Controller reconnects
    await mock_websocket_state.reconnect()
    assert hass.states.get("sensor.ssid_1").state == "0"

    # WLAN gets disabled
    wlan_1 = deepcopy(WLAN)
    wlan_1["enabled"] = False
    mock_websocket_message(message=MessageKey.WLAN_CONF_UPDATED, data=wlan_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ssid_1").state == STATE_UNAVAILABLE

    # WLAN gets re-enabled
    wlan_1["enabled"] = True
    mock_websocket_message(message=MessageKey.WLAN_CONF_UPDATED, data=wlan_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ssid_1").state == "0"


@pytest.mark.parametrize(
    (
        "entity_id",
        "expected_value",
        "changed_data",
        "expected_update_value",
    ),
    [
        (
            "dummy_usp_pdu_pro_outlet_2_outlet_power",
            "73.827",
            {"outlet_table": PDU_OUTLETS_UPDATE_DATA},
            "123.45",
        ),
        (
            "dummy_usp_pdu_pro_ac_power_budget",
            "1875.000",
            None,
            None,
        ),
        (
            "dummy_usp_pdu_pro_ac_power_consumption",
            "201.683",
            {"outlet_ac_power_consumption": "456.78"},
            "456.78",
        ),
    ],
)
@pytest.mark.parametrize("device_payload", [[PDU_DEVICE_1]])
@pytest.mark.usefixtures("config_entry_setup")
async def test_outlet_power_readings(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    entity_id: str,
    expected_value: str,
    changed_data: dict[str, Any] | None,
    expected_update_value: str | None,
) -> None:
    """Test the outlet power reporting on PDU devices."""
    assert len(hass.states.async_all()) == 13
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 7

    assert hass.states.get(f"sensor.{entity_id}").state == expected_value

    if changed_data is not None:
        updated_device_data = deepcopy(device_payload[0])
        updated_device_data.update(changed_data)

        mock_websocket_message(message=MessageKey.DEVICE, data=updated_device_data)
        await hass.async_block_till_done()

        assert hass.states.get(f"sensor.{entity_id}").state == expected_update_value


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 3,
                "device_id": "mock-id",
                "general_temperature": 30,
                "has_fan": True,
                "has_temperature": True,
                "fan_level": 0,
                "ip": "10.0.1.1",
                "last_seen": 1562600145,
                "mac": "00:00:00:00:01:01",
                "model": "US16P150",
                "name": "Device",
                "next_interval": 20,
                "overheating": True,
                "state": 1,
                "type": "usw",
                "upgradable": True,
                "uptime": 60,
                "version": "4.0.42.10433",
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_temperature(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that temperature sensors are working as expected."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3
    assert hass.states.get("sensor.device_temperature").state == "30"

    # Verify new event change temperature
    device = device_payload[0]
    device["general_temperature"] = 60
    mock_websocket_message(message=MessageKey.DEVICE, data=device)
    assert hass.states.get("sensor.device_temperature").state == "60"


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 3,
                "device_id": "mock-id",
                "general_temperature": 30,
                "has_fan": True,
                "has_temperature": True,
                "fan_level": 0,
                "ip": "10.0.1.1",
                "last_seen": 1562600145,
                "mac": "00:00:00:00:01:01",
                "model": "US16P150",
                "name": "Device",
                "next_interval": 20,
                "overheating": True,
                "state": 1,
                "type": "usw",
                "upgradable": True,
                "uptime": 60,
                "version": "4.0.42.10433",
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that state sensors are working as expected."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3

    device = device_payload[0]
    for i in list(map(int, DeviceState)):
        device["state"] = i
        mock_websocket_message(message=MessageKey.DEVICE, data=device)
        assert hass.states.get("sensor.device_state").state == DEVICE_STATES[i]


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "device_id": "mock-id",
                "mac": "00:00:00:00:01:01",
                "model": "US16P150",
                "name": "Device",
                "state": 1,
                "version": "4.0.42.10433",
                "system-stats": {"cpu": 5.8, "mem": 31.1, "uptime": 7316},
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_system_stats(
    hass: HomeAssistant,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that device stats sensors are working as expected."""
    assert len(hass.states.async_all()) == 8
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4

    assert hass.states.get("sensor.device_cpu_utilization").state == "5.8"
    assert hass.states.get("sensor.device_memory_utilization").state == "31.1"

    # Verify new event change system-stats
    device = device_payload[0]
    device["system-stats"] = {"cpu": 7.7, "mem": 33.3, "uptime": 7316}
    mock_websocket_message(message=MessageKey.DEVICE, data=device)

    assert hass.states.get("sensor.device_cpu_utilization").state == "7.7"
    assert hass.states.get("sensor.device_memory_utilization").state == "33.3"


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: False,
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        }
    ],
)
@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
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
                        "poe_enable": False,
                        "poe_mode": "auto",
                        "poe_power": "2.56",
                        "poe_voltage": "53.40",
                        "portconf_id": "1a1",
                        "port_poe": False,
                        "up": True,
                        "rx_bytes-r": 1151,
                        "tx_bytes-r": 5111,
                    },
                    {
                        "media": "GE",
                        "name": "Port 2",
                        "port_idx": 2,
                        "poe_class": "Class 4",
                        "poe_enable": False,
                        "poe_mode": "auto",
                        "poe_power": "2.56",
                        "poe_voltage": "53.40",
                        "portconf_id": "1a2",
                        "port_poe": False,
                        "up": True,
                        "rx_bytes-r": 1536,
                        "tx_bytes-r": 3615,
                    },
                ],
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
            }
        ]
    ],
)
async def test_bandwidth_port_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_setup: MockConfigEntry,
    config_entry_options: MappingProxyType[str, Any],
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that port bandwidth sensors are working as expected."""
    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    p1rx_reg_entry = entity_registry.async_get("sensor.mock_name_port_1_rx")
    assert p1rx_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    p1tx_reg_entry = entity_registry.async_get("sensor.mock_name_port_1_tx")
    assert p1tx_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(
        entity_id="sensor.mock_name_port_1_rx", disabled_by=None
    )
    entity_registry.async_update_entity(
        entity_id="sensor.mock_name_port_1_tx", disabled_by=None
    )
    entity_registry.async_update_entity(
        entity_id="sensor.mock_name_port_2_rx", disabled_by=None
    )
    entity_registry.async_update_entity(
        entity_id="sensor.mock_name_port_2_tx", disabled_by=None
    )
    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Validate state object
    assert len(hass.states.async_all()) == 9
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6

    # Verify sensor state
    assert hass.states.get("sensor.mock_name_port_1_rx").state == "0.00921"
    assert hass.states.get("sensor.mock_name_port_1_tx").state == "0.04089"
    assert hass.states.get("sensor.mock_name_port_2_rx").state == "0.01229"
    assert hass.states.get("sensor.mock_name_port_2_tx").state == "0.02892"

    # Verify state update
    device_1 = device_payload[0]
    device_1["port_table"][0]["rx_bytes-r"] = 3456000000
    device_1["port_table"][0]["tx_bytes-r"] = 7891000000

    mock_websocket_message(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_name_port_1_rx").state == "27648.00000"
    assert hass.states.get("sensor.mock_name_port_1_tx").state == "63128.00000"

    # Disable option
    options = config_entry_options.copy()
    options[CONF_ALLOW_BANDWIDTH_SENSORS] = False
    hass.config_entries.async_update_entry(config_entry_setup, options=options)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    assert hass.states.get("sensor.mock_name_uptime")
    assert hass.states.get("sensor.mock_name_state")
    assert hass.states.get("sensor.mock_name_port_1_rx") is None
    assert hass.states.get("sensor.mock_name_port_1_tx") is None
    assert hass.states.get("sensor.mock_name_port_2_rx") is None
    assert hass.states.get("sensor.mock_name_port_2_tx") is None


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "device_id": "mock-id1",
                "mac": "01:00:00:00:00:00",
                "model": "US16P150",
                "name": "Wired Device",
                "state": 1,
                "version": "4.0.42.10433",
            },
            {
                "device_id": "mock-id2",
                "mac": "02:00:00:00:00:00",
                "model": "US16P150",
                "name": "Wireless Device",
                "state": 1,
                "version": "4.0.42.10433",
            },
        ]
    ],
)
async def test_device_client_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    client_payload: dict[str, Any],
) -> None:
    """Verify that WLAN client sensors are working as expected."""
    client_payload += [
        {
            "hostname": "Wired client 1",
            "is_wired": True,
            "mac": "00:00:00:00:00:01",
            "oui": "Producer",
            "sw_mac": "01:00:00:00:00:00",
            "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        },
        {
            "hostname": "Wired client 2",
            "is_wired": True,
            "mac": "00:00:00:00:00:02",
            "oui": "Producer",
            "sw_mac": "01:00:00:00:00:00",
            "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        },
        {
            "is_wired": False,
            "mac": "00:00:00:00:00:03",
            "name": "Wireless client 1",
            "oui": "Producer",
            "ap_mac": "02:00:00:00:00:00",
            "sw_mac": "01:00:00:00:00:00",
            "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        },
    ]
    await config_entry_factory()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4

    ent_reg_entry = entity_registry.async_get("sensor.wired_device_clients")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    ent_reg_entry = entity_registry.async_get("sensor.wireless_device_clients")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(
        entity_id="sensor.wired_device_clients", disabled_by=None
    )
    entity_registry.async_update_entity(
        entity_id="sensor.wireless_device_clients", disabled_by=None
    )

    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    # Validate state object
    assert len(hass.states.async_all()) == 13
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6

    assert hass.states.get("sensor.wired_device_clients").state == "2"
    assert hass.states.get("sensor.wireless_device_clients").state == "1"

    # Verify state update - decreasing number
    wireless_client_1 = client_payload[2]
    wireless_client_1["last_seen"] = 0
    mock_websocket_message(message=MessageKey.CLIENT, data=wireless_client_1)

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wired_device_clients").state == "2"
    assert hass.states.get("sensor.wireless_device_clients").state == "0"


async def _test_uptime_entity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_websocket_message: WebsocketMessageMock,
    config_entry_factory: ConfigEntryFactoryType,
    payload: dict[str, Any],
    entity_id: str,
    message_key: MessageKey,
    initial_uptime: int,
    event_uptime: int,
    small_variation_uptime: int,
    new_uptime: int,
) -> None:
    """Verify that uptime entities are working as expected."""
    payload["uptime"] = initial_uptime
    freezer.move_to(datetime(2021, 1, 1, 1, 1, 0, tzinfo=dt_util.UTC))
    config_entry = await config_entry_factory()

    assert hass.states.get(entity_id).state == "2021-01-01T01:00:00+00:00"

    # Verify normal new event doesn't change uptime
    # 4 minutes have passed

    payload["uptime"] = event_uptime
    now = datetime(2021, 1, 1, 1, 4, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_websocket_message(message=message_key, data=payload)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "2021-01-01T01:00:00+00:00"

    # Verify small variation of uptime (<120 seconds) is ignored
    # 15 seconds variation after 8 minutes

    payload["uptime"] = small_variation_uptime
    now = datetime(2021, 1, 1, 1, 8, 15, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_websocket_message(message=message_key, data=payload)

    assert hass.states.get(entity_id).state == "2021-01-01T01:00:00+00:00"

    # Verify new event change uptime
    # 1 month has passed

    payload["uptime"] = new_uptime
    now = datetime(2021, 2, 1, 1, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_websocket_message(message=message_key, data=payload)
        await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "2021-02-01T01:00:00+00:00"

    return config_entry


@pytest.mark.parametrize("config_entry_options", [{CONF_ALLOW_UPTIME_SENSORS: True}])
@pytest.mark.parametrize("client_payload", [[WIRED_CLIENT]])
@pytest.mark.parametrize(
    ("initial_uptime", "event_uptime", "small_variation_uptime", "new_uptime"),
    [
        # Uptime listed in epoch time should never change
        (1609462800, 1609462800, 1609462800, 1612141200),
        # Uptime counted in seconds increases with every event
        (60, 240, 480, 60),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_client_uptime(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry_options: MappingProxyType[str, Any],
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    client_payload: list[dict[str, Any]],
    initial_uptime,
    event_uptime,
    small_variation_uptime,
    new_uptime,
) -> None:
    """Verify that client uptime sensors are working as expected."""
    config_entry = await _test_uptime_entity(
        hass,
        freezer,
        mock_websocket_message,
        config_entry_factory,
        payload=client_payload[0],
        entity_id="sensor.wired_client_uptime",
        message_key=MessageKey.CLIENT,
        initial_uptime=initial_uptime,
        event_uptime=event_uptime,
        small_variation_uptime=small_variation_uptime,
        new_uptime=new_uptime,
    )

    # Disable option
    options = deepcopy(config_entry_options)
    options[CONF_ALLOW_UPTIME_SENSORS] = False
    hass.config_entries.async_update_entry(config_entry, options=options)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wired_client_uptime") is None

    # Enable option
    options = deepcopy(config_entry_options)
    options[CONF_ALLOW_UPTIME_SENSORS] = True
    hass.config_entries.async_update_entry(config_entry, options=options)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wired_client_uptime")


@pytest.mark.parametrize("device_payload", [[DEVICE_1]])
async def test_device_uptime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    config_entry_factory: ConfigEntryFactoryType,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that device uptime sensors are working as expected."""
    await _test_uptime_entity(
        hass,
        freezer,
        mock_websocket_message,
        config_entry_factory,
        payload=device_payload[0],
        entity_id="sensor.mock_name_uptime",
        message_key=MessageKey.DEVICE,
        initial_uptime=60,
        event_uptime=240,
        small_variation_uptime=480,
        new_uptime=60,
    )


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 2,
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": "10:00:00:00:01:01",
                "last_seen": 1562600145,
                "model": "US16P150",
                "name": "mock-name",
                "port_overrides": [],
                "uptime_stats": {
                    "WAN": {
                        "availability": 100.0,
                        "latency_average": 39,
                        "monitors": [
                            {
                                "availability": 100.0,
                                "latency_average": 56,
                                "target": "www.microsoft.com",
                                "type": "icmp",
                            },
                            {
                                "availability": 100.0,
                                "latency_average": 53,
                                "target": "google.com",
                                "type": "icmp",
                            },
                            {
                                "availability": 100.0,
                                "latency_average": 30,
                                "target": "1.1.1.1",
                                "type": "icmp",
                            },
                        ],
                    },
                    "WAN2": {
                        "monitors": [
                            {
                                "availability": 0.0,
                                "target": "www.microsoft.com",
                                "type": "icmp",
                            },
                            {
                                "availability": 0.0,
                                "target": "google.com",
                                "type": "icmp",
                            },
                            {"availability": 0.0, "target": "1.1.1.1", "type": "icmp"},
                        ],
                    },
                },
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
            }
        ]
    ],
)
@pytest.mark.parametrize(
    ("monitor_id", "state", "updated_state", "index_to_update"),
    [
        # Microsoft
        ("microsoft_wan", "56", "20", 0),
        # Google
        ("google_wan", "53", "90", 1),
        # Cloudflare
        ("cloudflare_wan", "30", "80", 2),
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_wan_monitor_latency(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message: WebsocketMessageMock,
    device_payload: list[dict[str, Any]],
    monitor_id: str,
    state: str,
    updated_state: str,
    index_to_update: int,
) -> None:
    """Verify that wan latency sensors are working as expected."""
    entity_id = f"sensor.mock_name_{monitor_id}_latency"

    assert len(hass.states.async_all()) == 6
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    latency_entry = entity_registry.async_get(entity_id)
    assert latency_entry.disabled_by == RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)

    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 7
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3

    # Verify sensor state
    assert hass.states.get(entity_id).state == state

    # Verify state update
    device = device_payload[0]
    device["uptime_stats"]["WAN"]["monitors"][index_to_update]["latency_average"] = (
        updated_state
    )

    mock_websocket_message(message=MessageKey.DEVICE, data=device)

    assert hass.states.get(entity_id).state == updated_state


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 2,
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": "10:00:00:00:01:01",
                "last_seen": 1562600145,
                "model": "US16P150",
                "name": "mock-name",
                "port_overrides": [],
                "uptime_stats": {
                    "WAN": {
                        "monitors": [
                            {
                                "availability": 100.0,
                                "latency_average": 30,
                                "target": "1.2.3.4",
                                "type": "icmp",
                            },
                        ],
                    },
                    "WAN2": {
                        "monitors": [
                            {
                                "availability": 0.0,
                                "target": "www.microsoft.com",
                                "type": "icmp",
                            },
                            {
                                "availability": 0.0,
                                "target": "google.com",
                                "type": "icmp",
                            },
                            {"availability": 0.0, "target": "1.1.1.1", "type": "icmp"},
                        ],
                    },
                },
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_wan_monitor_latency_with_no_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Verify that wan latency sensors is not created if there is no data."""

    assert len(hass.states.async_all()) == 6
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    latency_entry = entity_registry.async_get("sensor.mock_name_google_wan_latency")
    assert latency_entry is None


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 2,
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": "10:00:00:00:01:01",
                "last_seen": 1562600145,
                "model": "US16P150",
                "name": "mock-name",
                "port_overrides": [],
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_wan_monitor_latency_with_no_uptime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Verify that wan latency sensors is not created if there is no data."""

    assert len(hass.states.async_all()) == 6
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    latency_entry = entity_registry.async_get("sensor.mock_name_google_wan_latency")
    assert latency_entry is None


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 3,
                "device_id": "mock-id",
                "has_fan": True,
                "fan_level": 0,
                "ip": "10.0.1.1",
                "last_seen": 1562600145,
                "mac": "00:00:00:00:01:01",
                "model": "US16P150",
                "name": "Device",
                "next_interval": 20,
                "overheating": True,
                "state": 1,
                "type": "usw",
                "upgradable": True,
                "uptime": 60,
                "version": "4.0.42.10433",
                "temperatures": [
                    {"name": "CPU", "type": "cpu", "value": 66.0},
                    {"name": "Local", "type": "board", "value": 48.75},
                    {"name": "PHY", "type": "board", "value": 50.25},
                ],
            }
        ]
    ],
)
@pytest.mark.parametrize(
    ("temperature_id", "state", "updated_state", "index_to_update"),
    [
        ("device_cpu", "66.0", "20", 0),
        ("device_local", "48.75", "90.64", 1),
        ("device_phy", "50.25", "80", 2),
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_temperatures(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message,
    device_payload: list[dict[str, Any]],
    temperature_id: str,
    state: str,
    updated_state: str,
    index_to_update: int,
) -> None:
    """Verify that device temperatures sensors are working as expected."""

    entity_id = f"sensor.device_{temperature_id}_temperature"

    assert len(hass.states.async_all()) == 6
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    temperature_entity = entity_registry.async_get(entity_id)
    assert temperature_entity.disabled_by == RegistryEntryDisabler.INTEGRATION

    # Enable entity
    entity_registry.async_update_entity(entity_id=entity_id, disabled_by=None)

    await hass.async_block_till_done()

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + timedelta(seconds=RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 7
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3

    # Verify sensor state
    assert hass.states.get(entity_id).state == state

    # # Verify state update
    device = device_payload[0]
    device["temperatures"][index_to_update]["value"] = updated_state

    mock_websocket_message(message=MessageKey.DEVICE, data=device)

    assert hass.states.get(entity_id).state == updated_state


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 2,
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": "10:00:00:00:01:01",
                "last_seen": 1562600145,
                "model": "US16P150",
                "name": "mock-name",
                "port_overrides": [],
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_with_no_temperature(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Verify that device temperature sensors is not created if there is no data."""

    assert len(hass.states.async_all()) == 6
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    temperature_entity = entity_registry.async_get(
        "sensor.device_device_cpu_temperature"
    )

    assert temperature_entity is None


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 2,
                "device_id": "mock-id",
                "ip": "10.0.1.1",
                "mac": "10:00:00:00:01:01",
                "last_seen": 1562600145,
                "model": "US16P150",
                "name": "mock-name",
                "port_overrides": [],
                "state": 1,
                "type": "usw",
                "version": "4.0.42.10433",
                "temperatures": [
                    {"name": "MEM", "type": "mem", "value": 66.0},
                ],
            }
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_with_no_matching_temperatures(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Verify that device temperature sensors is not created if there is no matching data."""

    assert len(hass.states.async_all()) == 6
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    temperature_entity = entity_registry.async_get(
        "sensor.device_device_cpu_temperature"
    )

    assert temperature_entity is None


@pytest.mark.parametrize(
    "device_payload",
    [
        [
            {
                "board_rev": 3,
                "device_id": "device-with-uplink",
                "ip": "10.0.1.1",
                "last_seen": 1562600145,
                "mac": "00:00:00:00:01:01",
                "model": "US16P150",
                "name": "Device",
                "next_interval": 20,
                "state": 1,
                "type": "usw",
                "upgradable": True,
                "uptime": 60,
                "version": "4.0.42.10433",
                "uplink": {
                    "uplink_mac": "00:00:00:00:00:02",
                    "port_idx": 1,
                },
            },
            {
                "board_rev": 3,
                "device_id": "device-without-uplink",
                "ip": "10.0.1.2",
                "last_seen": 1562600145,
                "mac": "00:00:00:00:01:02",
                "model": "US16P150",
                "name": "Other Device",
                "next_interval": 20,
                "state": 1,
                "type": "usw",
                "upgradable": True,
                "uptime": 60,
                "version": "4.0.42.10433",
                "uplink": {},
            },
        ],
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
async def test_device_uplink(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that uplink sensors are working as expected."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 5
    assert hass.states.get("sensor.device_uplink_mac").state == "00:00:00:00:00:02"
    assert (
        entity_registry.async_get("sensor.device_uplink_mac").entity_category
        is EntityCategory.DIAGNOSTIC
    )

    # Verify new event change temperature
    device = device_payload[0]
    device["uplink"]["uplink_mac"] = "00:00:00:00:00:03"
    mock_websocket_message(message=MessageKey.DEVICE, data=device)
    assert hass.states.get("sensor.device_uplink_mac").state == "00:00:00:00:00:03"
