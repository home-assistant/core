"""UniFi Network sensor platform tests."""

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any
from unittest.mock import patch

from aiounifi.models.device import DeviceState
from aiounifi.models.message import MessageKey
from freezegun.api import FrozenDateTimeFactory, freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    SCAN_INTERVAL,
    SensorDeviceClass,
    SensorStateClass,
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
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY, ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed

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
@pytest.mark.parametrize(
    "client_payload",
    [
        [
            {
                "hostname": "Wired client",
                "is_wired": True,
                "mac": "00:00:00:00:00:01",
                "oui": "Producer",
                "wired-rx_bytes-r": 1234000000,
                "wired-tx_bytes-r": 5678000000,
            },
            {
                "is_wired": False,
                "mac": "00:00:00:00:00:02",
                "name": "Wireless client",
                "oui": "Producer",
                "rx_bytes-r": 2345000000.0,
                "tx_bytes-r": 6789000000.0,
            },
        ]
    ],
)
async def test_bandwidth_sensors(
    hass: HomeAssistant,
    mock_websocket_message,
    config_entry_options: MappingProxyType[str, Any],
    config_entry_setup: ConfigEntry,
    client_payload: list[dict[str, Any]],
) -> None:
    """Verify that bandwidth sensors are working as expected."""
    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4

    # Verify sensor attributes and state

    wrx_sensor = hass.states.get("sensor.wired_client_rx")
    assert wrx_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_RATE
    assert wrx_sensor.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert wrx_sensor.state == "1234.0"

    wtx_sensor = hass.states.get("sensor.wired_client_tx")
    assert wtx_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_RATE
    assert wtx_sensor.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert wtx_sensor.state == "5678.0"

    wlrx_sensor = hass.states.get("sensor.wireless_client_rx")
    assert wlrx_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_RATE
    assert wlrx_sensor.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert wlrx_sensor.state == "2345.0"

    wltx_sensor = hass.states.get("sensor.wireless_client_tx")
    assert wltx_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_RATE
    assert wltx_sensor.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert wltx_sensor.state == "6789.0"

    # Verify state update
    wireless_client = client_payload[1]
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
    [
        {
            CONF_ALLOW_BANDWIDTH_SENSORS: False,
            CONF_ALLOW_UPTIME_SENSORS: True,
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        }
    ],
)
@pytest.mark.parametrize(
    "client_payload",
    [
        [
            {
                "mac": "00:00:00:00:00:01",
                "name": "client1",
                "oui": "Producer",
                "uptime": 0,
            }
        ]
    ],
)
@pytest.mark.parametrize(
    ("initial_uptime", "event_uptime", "new_uptime"),
    [
        # Uptime listed in epoch time should never change
        (1609462800, 1609462800, 1612141200),
        # Uptime counted in seconds increases with every event
        (60, 64, 60),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_uptime_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_websocket_message,
    config_entry_options: MappingProxyType[str, Any],
    config_entry_factory: Callable[[], ConfigEntry],
    client_payload: list[dict[str, Any]],
    initial_uptime,
    event_uptime,
    new_uptime,
) -> None:
    """Verify that uptime sensors are working as expected."""
    uptime_client = client_payload[0]
    uptime_client["uptime"] = initial_uptime
    freezer.move_to(datetime(2021, 1, 1, 1, 1, 0, tzinfo=dt_util.UTC))
    config_entry = await config_entry_factory()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    assert hass.states.get("sensor.client1_uptime").state == "2021-01-01T01:00:00+00:00"
    assert (
        entity_registry.async_get("sensor.client1_uptime").entity_category
        is EntityCategory.DIAGNOSTIC
    )

    # Verify normal new event doesn't change uptime
    # 4 seconds has passed
    uptime_client["uptime"] = event_uptime
    now = datetime(2021, 1, 1, 1, 1, 4, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_websocket_message(message=MessageKey.CLIENT, data=uptime_client)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.client1_uptime").state == "2021-01-01T01:00:00+00:00"

    # Verify new event change uptime
    # 1 month has passed
    uptime_client["uptime"] = new_uptime
    now = datetime(2021, 2, 1, 1, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_websocket_message(message=MessageKey.CLIENT, data=uptime_client)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.client1_uptime").state == "2021-02-01T01:00:00+00:00"

    # Disable option
    options = deepcopy(config_entry_options)
    options[CONF_ALLOW_UPTIME_SENSORS] = False
    hass.config_entries.async_update_entry(config_entry, options=options)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    assert hass.states.get("sensor.client1_uptime") is None

    # Enable option
    options = deepcopy(config_entry_options)
    options[CONF_ALLOW_UPTIME_SENSORS] = True
    with patch("homeassistant.util.dt.now", return_value=now):
        hass.config_entries.async_update_entry(config_entry, options=options)
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    assert hass.states.get("sensor.client1_uptime")


@pytest.mark.parametrize(
    "config_entry_options",
    [{CONF_ALLOW_BANDWIDTH_SENSORS: True, CONF_ALLOW_UPTIME_SENSORS: True}],
)
@pytest.mark.parametrize(
    "client_payload",
    [
        [
            {
                "hostname": "Wired client",
                "is_wired": True,
                "mac": "00:00:00:00:00:01",
                "oui": "Producer",
                "wired-rx_bytes": 1234000000,
                "wired-tx_bytes": 5678000000,
                "uptime": 1600094505,
            },
            {
                "is_wired": False,
                "mac": "00:00:00:00:00:02",
                "name": "Wireless client",
                "oui": "Producer",
                "rx_bytes": 2345000000,
                "tx_bytes": 6789000000,
                "uptime": 60,
            },
        ]
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_remove_sensors(
    hass: HomeAssistant, mock_websocket_message, client_payload: list[dict[str, Any]]
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
    mock_websocket_message,
    mock_websocket_state,
) -> None:
    """Test the update_items function with some clients."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    ent_reg_entry = entity_registry.async_get("sensor.mock_name_port_1_poe_power")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert ent_reg_entry.entity_category is EntityCategory.DIAGNOSTIC

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
    entity_registry: er.EntityRegistry,
    mock_websocket_message,
    mock_websocket_state,
    config_entry_factory: Callable[[], ConfigEntry],
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

    ent_reg_entry = entity_registry.async_get("sensor.ssid_1")
    assert ent_reg_entry.unique_id == "wlan_clients-012345678910111213141516"
    assert ent_reg_entry.entity_category is EntityCategory.DIAGNOSTIC

    # Validate state object
    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1 is not None
    assert ssid_1.state == "1"

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
        "expected_unique_id",
        "expected_value",
        "changed_data",
        "expected_update_value",
    ),
    [
        (
            "dummy_usp_pdu_pro_outlet_2_outlet_power",
            "outlet_power-01:02:03:04:05:ff_2",
            "73.827",
            {"outlet_table": PDU_OUTLETS_UPDATE_DATA},
            "123.45",
        ),
        (
            "dummy_usp_pdu_pro_ac_power_budget",
            "ac_power_budget-01:02:03:04:05:ff",
            "1875.000",
            None,
            None,
        ),
        (
            "dummy_usp_pdu_pro_ac_power_consumption",
            "ac_power_conumption-01:02:03:04:05:ff",
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
    entity_registry: er.EntityRegistry,
    mock_websocket_message,
    device_payload: list[dict[str, Any]],
    entity_id: str,
    expected_unique_id: str,
    expected_value: any,
    changed_data: dict | None,
    expected_update_value: any,
) -> None:
    """Test the outlet power reporting on PDU devices."""
    assert len(hass.states.async_all()) == 13
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 7

    ent_reg_entry = entity_registry.async_get(f"sensor.{entity_id}")
    assert ent_reg_entry.unique_id == expected_unique_id
    assert ent_reg_entry.entity_category is EntityCategory.DIAGNOSTIC

    sensor_data = hass.states.get(f"sensor.{entity_id}")
    assert sensor_data.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    assert sensor_data.state == expected_value

    if changed_data is not None:
        updated_device_data = deepcopy(device_payload[0])
        updated_device_data.update(changed_data)

        mock_websocket_message(message=MessageKey.DEVICE, data=updated_device_data)
        await hass.async_block_till_done()

        sensor_data = hass.states.get(f"sensor.{entity_id}")
        assert sensor_data.state == expected_update_value


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
            }
        ]
    ],
)
async def test_device_uptime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_websocket_message,
    config_entry_factory: Callable[[], ConfigEntry],
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that uptime sensors are working as expected."""
    now = datetime(2021, 1, 1, 1, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        await config_entry_factory()
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2
    assert hass.states.get("sensor.device_uptime").state == "2021-01-01T01:00:00+00:00"

    assert (
        entity_registry.async_get("sensor.device_uptime").entity_category
        is EntityCategory.DIAGNOSTIC
    )

    # Verify normal new event doesn't change uptime
    # 4 seconds has passed
    device = device_payload[0]
    device["uptime"] = 64
    now = datetime(2021, 1, 1, 1, 1, 4, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_websocket_message(message=MessageKey.DEVICE, data=device)

    assert hass.states.get("sensor.device_uptime").state == "2021-01-01T01:00:00+00:00"

    # Verify new event change uptime
    # 1 month has passed

    device["uptime"] = 60
    now = datetime(2021, 2, 1, 1, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_websocket_message(message=MessageKey.DEVICE, data=device)

    assert hass.states.get("sensor.device_uptime").state == "2021-02-01T01:00:00+00:00"


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
    entity_registry: er.EntityRegistry,
    mock_websocket_message,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that temperature sensors are working as expected."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3
    assert hass.states.get("sensor.device_temperature").state == "30"
    assert (
        entity_registry.async_get("sensor.device_temperature").entity_category
        is EntityCategory.DIAGNOSTIC
    )

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
    mock_websocket_message,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that state sensors are working as expected."""
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3
    assert (
        entity_registry.async_get("sensor.device_state").entity_category
        is EntityCategory.DIAGNOSTIC
    )

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
    entity_registry: er.EntityRegistry,
    mock_websocket_message,
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that device stats sensors are working as expected."""
    assert len(hass.states.async_all()) == 8
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4

    assert hass.states.get("sensor.device_cpu_utilization").state == "5.8"
    assert hass.states.get("sensor.device_memory_utilization").state == "31.1"

    assert (
        entity_registry.async_get("sensor.device_cpu_utilization").entity_category
        is EntityCategory.DIAGNOSTIC
    )

    assert (
        entity_registry.async_get("sensor.device_memory_utilization").entity_category
        is EntityCategory.DIAGNOSTIC
    )

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
    mock_websocket_message,
    config_entry_setup: ConfigEntry,
    config_entry_options: MappingProxyType[str, Any],
    device_payload: list[dict[str, Any]],
) -> None:
    """Verify that port bandwidth sensors are working as expected."""
    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 2

    p1rx_reg_entry = entity_registry.async_get("sensor.mock_name_port_1_rx")
    assert p1rx_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert p1rx_reg_entry.entity_category is EntityCategory.DIAGNOSTIC

    p1tx_reg_entry = entity_registry.async_get("sensor.mock_name_port_1_tx")
    assert p1tx_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert p1tx_reg_entry.entity_category is EntityCategory.DIAGNOSTIC

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

    # Verify sensor attributes and state
    p1rx_sensor = hass.states.get("sensor.mock_name_port_1_rx")
    assert p1rx_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_RATE
    assert p1rx_sensor.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert p1rx_sensor.state == "0.00921"

    p1tx_sensor = hass.states.get("sensor.mock_name_port_1_tx")
    assert p1tx_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_RATE
    assert p1tx_sensor.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert p1tx_sensor.state == "0.04089"

    p2rx_sensor = hass.states.get("sensor.mock_name_port_2_rx")
    assert p2rx_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_RATE
    assert p2rx_sensor.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert p2rx_sensor.state == "0.01229"

    p2tx_sensor = hass.states.get("sensor.mock_name_port_2_tx")
    assert p2tx_sensor.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.DATA_RATE
    assert p2tx_sensor.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT
    assert p2tx_sensor.state == "0.02892"

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
    config_entry_factory,
    mock_websocket_message,
    client_payload,
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
    assert ent_reg_entry.entity_category is EntityCategory.DIAGNOSTIC
    assert ent_reg_entry.unique_id == "device_clients-01:00:00:00:00:00"

    ent_reg_entry = entity_registry.async_get("sensor.wireless_device_clients")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert ent_reg_entry.entity_category is EntityCategory.DIAGNOSTIC
    assert ent_reg_entry.unique_id == "device_clients-02:00:00:00:00:00"

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
    "mac": "00:00:00:00:00:01",
    "name": "Wireless client",
    "oui": "Producer",
    "rx_bytes-r": 2345000000.0,
    "tx_bytes-r": 6789000000.0,
    "uptime": 60,
}


@pytest.mark.parametrize(
    "config_entry_options",
    [
        {
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        }
    ],
)
@pytest.mark.parametrize(
    ("client_payload", "entity_id", "unique_id_prefix"),
    [
        ([WIRED_CLIENT], "sensor.wired_client_rx", "rx-"),
        ([WIRED_CLIENT], "sensor.wired_client_tx", "tx-"),
        ([WIRED_CLIENT], "sensor.wired_client_uptime", "uptime-"),
        ([WIRELESS_CLIENT], "sensor.wireless_client_rx", "rx-"),
        ([WIRELESS_CLIENT], "sensor.wireless_client_tx", "tx-"),
        ([WIRELESS_CLIENT], "sensor.wireless_client_uptime", "uptime-"),
    ],
)
@pytest.mark.usefixtures("config_entry_setup")
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time("2021-01-01 01:01:00")
async def test_sensor_sources(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
    unique_id_prefix: str,
) -> None:
    """Test sensor sources and the entity description."""
    ent_reg_entry = entity_registry.async_get(entity_id)
    assert ent_reg_entry.unique_id.startswith(unique_id_prefix)
    assert ent_reg_entry.unique_id == snapshot
    assert ent_reg_entry.entity_category == snapshot

    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_DEVICE_CLASS) == snapshot
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == snapshot
    assert state.attributes.get(ATTR_STATE_CLASS) == snapshot
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == snapshot
    assert state.state == snapshot
