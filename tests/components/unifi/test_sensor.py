"""UniFi sensor platform tests."""

from datetime import datetime
from unittest.mock import patch

from aiounifi.controller import MESSAGE_CLIENT, MESSAGE_CLIENT_REMOVED
import pytest

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
import homeassistant.util.dt as dt_util

from .test_controller import setup_unifi_integration


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


async def test_bandwidth_sensors(hass, aioclient_mock, mock_unifi_websocket):
    """Verify that bandwidth sensors are working as expected."""
    wired_client = {
        "hostname": "Wired client",
        "is_wired": True,
        "mac": "00:00:00:00:00:01",
        "oui": "Producer",
        "wired-rx_bytes": 1234000000,
        "wired-tx_bytes": 5678000000,
    }
    wireless_client = {
        "is_wired": False,
        "mac": "00:00:00:00:00:02",
        "name": "Wireless client",
        "oui": "Producer",
        "rx_bytes": 2345000000,
        "tx_bytes": 6789000000,
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

    # Verify state update

    wireless_client["rx_bytes"] = 3456000000
    wireless_client["tx_bytes"] = 7891000000

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [wireless_client],
        }
    )
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

    # Try to add the sensors again, using a signal

    clients_connected = {wired_client["mac"], wireless_client["mac"]}
    devices_connected = set()

    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    async_dispatcher_send(
        hass,
        controller.signal_update,
        clients_connected,
        devices_connected,
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 5
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 4


@pytest.mark.parametrize(
    "initial_uptime,event_uptime,new_uptime",
    [
        # Uptime listed in epoch time should never change
        (1609462800, 1609462800, 1612141200),
        # Uptime counted in seconds increases with every event
        (60, 64, 60),
    ],
)
async def test_uptime_sensors(
    hass,
    aioclient_mock,
    mock_unifi_websocket,
    initial_uptime,
    event_uptime,
    new_uptime,
):
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

    # Verify normal new event doesn't change uptime
    # 4 seconds has passed

    uptime_client["uptime"] = event_uptime
    now = datetime(2021, 1, 1, 1, 1, 4, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_unifi_websocket(
            data={
                "meta": {"message": MESSAGE_CLIENT},
                "data": [uptime_client],
            }
        )
        await hass.async_block_till_done()

    assert hass.states.get("sensor.client1_uptime").state == "2021-01-01T01:00:00+00:00"

    # Verify new event change uptime
    # 1 month has passed

    uptime_client["uptime"] = new_uptime
    now = datetime(2021, 2, 1, 1, 1, 0, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.now", return_value=now):
        mock_unifi_websocket(
            data={
                "meta": {"message": MESSAGE_CLIENT},
                "data": [uptime_client],
            }
        )
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

    # Try to add the sensors again, using a signal

    clients_connected = {uptime_client["mac"]}
    devices_connected = set()

    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    async_dispatcher_send(
        hass,
        controller.signal_update,
        clients_connected,
        devices_connected,
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2
    assert len(hass.states.async_entity_ids(SENSOR_DOMAIN)) == 1


async def test_remove_sensors(hass, aioclient_mock, mock_unifi_websocket):
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

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT_REMOVED},
            "data": [wired_client],
        }
    )
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
