"""UniFi sensor platform tests."""
from copy import deepcopy

from aiounifi.controller import MESSAGE_CLIENT, MESSAGE_CLIENT_REMOVED
from aiounifi.websocket import SIGNAL_DATA

from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.unifi.const import (
    CONF_ALLOW_BANDWIDTH_SENSORS,
    CONF_ALLOW_UPTIME_SENSORS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .test_controller import setup_unifi_integration

CLIENTS = [
    {
        "hostname": "Wired client hostname",
        "ip": "10.0.0.1",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
        "name": "Wired client name",
        "oui": "Producer",
        "sw_mac": "00:00:00:00:01:01",
        "sw_port": 1,
        "wired-rx_bytes": 1234000000,
        "wired-tx_bytes": 5678000000,
        "uptime": 1600094505,
    },
    {
        "hostname": "Wireless client hostname",
        "ip": "10.0.0.2",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
        "name": "Wireless client name",
        "oui": "Producer",
        "sw_mac": "00:00:00:00:01:01",
        "sw_port": 2,
        "rx_bytes": 1234000000,
        "tx_bytes": 5678000000,
        "uptime": 1600094505,
    },
]


async def test_no_clients(hass, aioclient_mock):
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


async def test_sensors(hass, aioclient_mock):
    """Test the update_items function with some clients."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        },
        clients_response=CLIENTS,
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6

    wired_client_rx = hass.states.get("sensor.wired_client_name_rx")
    assert wired_client_rx.state == "1234.0"

    wired_client_tx = hass.states.get("sensor.wired_client_name_tx")
    assert wired_client_tx.state == "5678.0"

    wired_client_uptime = hass.states.get("sensor.wired_client_name_uptime")
    assert wired_client_uptime.state == "2020-09-14T14:41:45+00:00"

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx.state == "1234.0"

    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx.state == "5678.0"

    wireless_client_uptime = hass.states.get("sensor.wireless_client_name_uptime")
    assert wireless_client_uptime.state == "2020-09-14T14:41:45+00:00"

    clients = deepcopy(CLIENTS)
    clients[0]["is_wired"] = False
    clients[1]["rx_bytes"] = 2345000000
    clients[1]["tx_bytes"] = 6789000000
    clients[1]["uptime"] = 1600180860

    event = {"meta": {"message": MESSAGE_CLIENT}, "data": clients}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx.state == "2345.0"

    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx.state == "6789.0"

    wireless_client_uptime = hass.states.get("sensor.wireless_client_name_uptime")
    assert wireless_client_uptime.state == "2020-09-15T14:41:00+00:00"

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_ALLOW_BANDWIDTH_SENSORS: False,
            CONF_ALLOW_UPTIME_SENSORS: False,
        },
    )
    await hass.async_block_till_done()

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx is None

    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx is None

    wired_client_uptime = hass.states.get("sensor.wired_client_name_uptime")
    assert wired_client_uptime is None

    wireless_client_uptime = hass.states.get("sensor.wireless_client_name_uptime")
    assert wireless_client_uptime is None

    hass.config_entries.async_update_entry(
        config_entry,
        options={
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
        },
    )
    await hass.async_block_till_done()

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx.state == "2345.0"

    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx.state == "6789.0"

    wireless_client_uptime = hass.states.get("sensor.wireless_client_name_uptime")
    assert wireless_client_uptime.state == "2020-09-15T14:41:00+00:00"

    wired_client_uptime = hass.states.get("sensor.wired_client_name_uptime")
    assert wired_client_uptime.state == "2020-09-14T14:41:45+00:00"

    # Try to add the sensors again, using a signal
    clients_connected = set()
    devices_connected = set()

    clients_connected.add(clients[0]["mac"])
    clients_connected.add(clients[1]["mac"])

    async_dispatcher_send(
        hass,
        controller.signal_update,
        clients_connected,
        devices_connected,
    )

    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6


async def test_remove_sensors(hass, aioclient_mock):
    """Test the remove_items function with some clients."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_ALLOW_BANDWIDTH_SENSORS: True,
            CONF_ALLOW_UPTIME_SENSORS: True,
        },
        clients_response=CLIENTS,
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 6
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    wired_client_rx = hass.states.get("sensor.wired_client_name_rx")
    assert wired_client_rx is not None
    wired_client_tx = hass.states.get("sensor.wired_client_name_tx")
    assert wired_client_tx is not None

    wired_client_uptime = hass.states.get("sensor.wired_client_name_uptime")
    assert wired_client_uptime is not None

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx is not None
    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx is not None

    wireless_client_uptime = hass.states.get("sensor.wireless_client_name_uptime")
    assert wireless_client_uptime is not None

    controller.api.websocket._data = {
        "meta": {"message": MESSAGE_CLIENT_REMOVED},
        "data": [CLIENTS[0]],
    }
    controller.api.session_handler(SIGNAL_DATA)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 3
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    wired_client_rx = hass.states.get("sensor.wired_client_name_rx")
    assert wired_client_rx is None
    wired_client_tx = hass.states.get("sensor.wired_client_name_tx")
    assert wired_client_tx is None

    wired_client_uptime = hass.states.get("sensor.wired_client_name_uptime")
    assert wired_client_uptime is None

    wireless_client_rx = hass.states.get("sensor.wireless_client_name_rx")
    assert wireless_client_rx is not None
    wireless_client_tx = hass.states.get("sensor.wireless_client_name_tx")
    assert wireless_client_tx is not None

    wireless_client_uptime = hass.states.get("sensor.wireless_client_name_uptime")
    assert wireless_client_uptime is not None
