"""UniFi Network sensor platform tests."""
from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from aiounifi.models.message import MessageKey
from aiounifi.websocket import WebsocketState
import pytest

from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
)
from homeassistant.config_entries import RELOAD_AFTER_UPDATE_DELAY
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_UNAVAILABLE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DEFAULT_SCAN_INTERVAL
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
import homeassistant.util.dt as dt_util

from .test_controller import setup_unifi_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

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


async def test_no_clients(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the update_clients function when no clients are found."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
        },
    )

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0


async def test_bandwidth_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Verify that bandwidth sensors are working as expected."""
    wired_client = {
        "hostname": "Wired client",
        "is_wired": True,
        "mac": "00:00:00:00:00:01",
        "oui": "Producer",
        "wired-rx_bytes-r": 1234000000,
        "wired-tx_bytes-r": 5678000000,
    }
    wireless_client = {
        "is_wired": False,
        "mac": "00:00:00:00:00:02",
        "name": "Wireless client",
        "oui": "Producer",
        "rx_bytes-r": 2345000000,
        "tx_bytes-r": 6789000000,
    }
    options = {
        CONF_ALLOW_BANDWIDTH_SENSORS: True,
        CONF_ALLOW_UPTIME_SENSORS: False,
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
    }

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options=options,
        clients_response=[wired_client, wireless_client],
    )

    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    assert hass.states.get("sensor.wired_client_rx").state == "1234.0"
    assert hass.states.get("sensor.wired_client_tx").state == "5678.0"
    assert hass.states.get("sensor.wireless_client_rx").state == "2345.0"
    assert hass.states.get("sensor.wireless_client_tx").state == "6789.0"

    ent_reg = er.async_get(hass)
    assert (
        ent_reg.async_get("sensor.wired_client_rx").entity_category
        is EntityCategory.DIAGNOSTIC
    )

    # Verify state update

    wireless_client["rx_bytes-r"] = 3456000000
    wireless_client["tx_bytes-r"] = 7891000000

    mock_unifi_websocket(message=MessageKey.CLIENT, data=wireless_client)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wireless_client_rx").state == "3456.0"
    assert hass.states.get("sensor.wireless_client_tx").state == "7891.0"

    # Disable option

    options[CONF_ALLOW_BANDWIDTH_SENSORS] = False
    hass.config_entries.async_update_entry(config_entry, options=options.copy())
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    assert hass.states.get("sensor.wireless_client_rx") is None
    assert hass.states.get("sensor.wireless_client_tx") is None
    assert hass.states.get("sensor.wired_client_rx") is None
    assert hass.states.get("sensor.wired_client_tx") is None

    # Enable option

    options[CONF_ALLOW_BANDWIDTH_SENSORS] = True
    hass.config_entries.async_update_entry(config_entry, options=options.copy())
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4
    assert hass.states.get("sensor.wireless_client_rx")
    assert hass.states.get("sensor.wireless_client_tx")
    assert hass.states.get("sensor.wired_client_rx")
    assert hass.states.get("sensor.wired_client_tx")


@pytest.mark.parametrize(
    ("initial_uptime", "event_uptime", "new_uptime"),
    [
        # Uptime listed in epoch time should never change
        (1609462800, 1609462800, 1612141200),
        # Uptime counted in seconds increases with every event
        (60, 64, 60),
    ],
)
async def test_uptime_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_unifi_websocket,
    entity_registry_enabled_by_default: None,
    initial_uptime,
    event_uptime,
    new_uptime,
) -> None:
    """Verify that uptime sensors are working as expected."""
    uptime_client = {
        "mac": "00:00:00:00:00:01",
        "name": "client1",
        "oui": "Producer",
        "uptime": initial_uptime,
    }
    options = {
        CONF_ALLOW_BANDWIDTH_SENSORS: False,
        CONF_ALLOW_UPTIME_SENSORS: True,
        CONF_TRACK_CLIENTS: False,
        CONF_TRACK_DEVICES: False,
    }

    now = datetime(2021, 1, 1, 1, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        config_entry = await setup_unifi_integration(
            hass,
            aioclient_mock,
            options=options,
            clients_response=[uptime_client],
        )

    assert len(hass.states.async_all()) == 2
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    assert hass.states.get("sensor.client1_uptime").state == "2021-01-01T01:00:00+00:00"

    ent_reg = er.async_get(hass)
    assert (
        ent_reg.async_get("sensor.client1_uptime").entity_category
        is EntityCategory.DIAGNOSTIC
    )

    # Verify normal new event doesn't change uptime
    # 4 seconds has passed

    uptime_client["uptime"] = event_uptime
    now = datetime(2021, 1, 1, 1, 1, 4, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_unifi_websocket(message=MessageKey.CLIENT, data=uptime_client)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.client1_uptime").state == "2021-01-01T01:00:00+00:00"

    # Verify new event change uptime
    # 1 month has passed

    uptime_client["uptime"] = new_uptime
    now = datetime(2021, 2, 1, 1, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_unifi_websocket(message=MessageKey.CLIENT, data=uptime_client)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.client1_uptime").state == "2021-02-01T01:00:00+00:00"

    # Disable option

    options[CONF_ALLOW_UPTIME_SENSORS] = False
    hass.config_entries.async_update_entry(config_entry, options=options.copy())
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0
    assert hass.states.get("sensor.client1_uptime") is None

    # Enable option

    options[CONF_ALLOW_UPTIME_SENSORS] = True
    with patch("homeassistant.util.dt.now", return_value=now):
        hass.config_entries.async_update_entry(config_entry, options=options.copy())
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1
    assert hass.states.get("sensor.client1_uptime")


async def test_remove_sensors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_unifi_websocket,
    entity_registry_enabled_by_default: None,
) -> None:
    """Verify removing of clients work as expected."""
    wired_client = {
        "hostname": "Wired client",
        "is_wired": True,
        "mac": "00:00:00:00:00:01",
        "oui": "Producer",
        "wired-rx_bytes": 1234000000,
        "wired-tx_bytes": 5678000000,
        "uptime": 1600094505,
    }
    wireless_client = {
        "is_wired": False,
        "mac": "00:00:00:00:00:02",
        "name": "Wireless client",
        "oui": "Producer",
        "rx_bytes": 2345000000,
        "tx_bytes": 6789000000,
        "uptime": 60,
    }

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
        },
        clients_response=[wired_client, wireless_client],
    )

    assert len(hass.states.async_all()) == 9
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("sensor.wired_client_rx")
    assert hass.states.get("sensor.wired_client_tx")
    assert hass.states.get("sensor.wired_client_uptime")
    assert hass.states.get("sensor.wireless_client_rx")
    assert hass.states.get("sensor.wireless_client_tx")
    assert hass.states.get("sensor.wireless_client_uptime")

    # Remove wired client

    mock_unifi_websocket(message=MessageKey.CLIENT_REMOVED, data=wired_client)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert hass.states.get("sensor.wired_client_rx") is None
    assert hass.states.get("sensor.wired_client_tx") is None
    assert hass.states.get("sensor.wired_client_uptime") is None
    assert hass.states.get("sensor.wireless_client_rx")
    assert hass.states.get("sensor.wireless_client_tx")
    assert hass.states.get("sensor.wireless_client_uptime")


async def test_poe_port_switches(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Test the update_items function with some clients."""
    await setup_unifi_integration(hass, aioclient_mock, devices_response=[DEVICE_1])
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 0

    ent_reg = er.async_get(hass)
    ent_reg_entry = ent_reg.async_get("sensor.mock_name_port_1_poe_power")
    assert ent_reg_entry.disabled_by == RegistryEntryDisabler.INTEGRATION
    assert ent_reg_entry.entity_category is EntityCategory.DIAGNOSTIC

    # Enable entity
    ent_reg.async_update_entity(
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
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mock_name_port_1_poe_power").state == "5.12"

    # PoE is disabled
    device_1 = deepcopy(DEVICE_1)
    device_1["port_table"][0]["poe_mode"] = "off"
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mock_name_port_1_poe_power").state == "0"

    # Availability signalling

    # Controller disconnects
    mock_unifi_websocket(state=WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.mock_name_port_1_poe_power").state == STATE_UNAVAILABLE
    )

    # Controller reconnects
    mock_unifi_websocket(state=WebsocketState.RUNNING)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mock_name_port_1_poe_power")

    # Device gets disabled
    device_1["disabled"] = True
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.mock_name_port_1_poe_power").state == STATE_UNAVAILABLE
    )

    # Device gets re-enabled
    device_1["disabled"] = False
    mock_unifi_websocket(message=MessageKey.DEVICE, data=device_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.mock_name_port_1_poe_power")


async def test_wlan_client_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_unifi_websocket
) -> None:
    """Verify that WLAN client sensors are working as expected."""
    wireless_client_1 = {
        "essid": "SSID 1",
        "is_wired": False,
        "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        "mac": "00:00:00:00:00:01",
        "name": "Wireless client",
        "oui": "Producer",
        "rx_bytes-r": 2345000000,
        "tx_bytes-r": 6789000000,
    }
    wireless_client_2 = {
        "essid": "SSID 2",
        "is_wired": False,
        "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        "mac": "00:00:00:00:00:02",
        "name": "Wireless client2",
        "oui": "Producer2",
        "rx_bytes-r": 2345000000,
        "tx_bytes-r": 6789000000,
    }

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        clients_response=[wireless_client_1, wireless_client_2],
        wlans_response=[WLAN],
    )

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1

    ent_reg = er.async_get(hass)
    ent_reg_entry = ent_reg.async_get("sensor.ssid_1")
    assert ent_reg_entry.unique_id == "wlan_clients-012345678910111213141516"
    assert ent_reg_entry.entity_category is EntityCategory.DIAGNOSTIC

    # Validate state object
    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1 is not None
    assert ssid_1.state == "1"

    # Verify state update - increasing number

    wireless_client_1["essid"] = "SSID 1"
    wireless_client_2["essid"] = "SSID 1"

    mock_unifi_websocket(message=MessageKey.CLIENT, data=wireless_client_1)
    mock_unifi_websocket(message=MessageKey.CLIENT, data=wireless_client_2)
    await hass.async_block_till_done()

    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1.state == "1"

    async_fire_time_changed(hass, datetime.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1.state == "2"

    # Verify state update - decreasing number

    wireless_client_1["essid"] = "SSID"
    mock_unifi_websocket(message=MessageKey.CLIENT, data=wireless_client_1)

    async_fire_time_changed(hass, datetime.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1.state == "1"

    # Verify state update - decreasing number

    wireless_client_2["last_seen"] = 0
    mock_unifi_websocket(message=MessageKey.CLIENT, data=wireless_client_2)

    async_fire_time_changed(hass, datetime.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    ssid_1 = hass.states.get("sensor.ssid_1")
    assert ssid_1.state == "0"

    # Availability signalling

    # Controller disconnects
    mock_unifi_websocket(state=WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ssid_1").state == STATE_UNAVAILABLE

    # Controller reconnects
    mock_unifi_websocket(state=WebsocketState.RUNNING)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ssid_1").state == "0"

    # WLAN gets disabled
    wlan_1 = deepcopy(WLAN)
    wlan_1["enabled"] = False
    mock_unifi_websocket(message=MessageKey.WLAN_CONF_UPDATED, data=wlan_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ssid_1").state == STATE_UNAVAILABLE

    # WLAN gets re-enabled
    wlan_1["enabled"] = True
    mock_unifi_websocket(message=MessageKey.WLAN_CONF_UPDATED, data=wlan_1)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.ssid_1").state == "0"
