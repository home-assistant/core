"""The tests for the UniFi device tracker platform."""

from datetime import timedelta
from unittest.mock import patch

from aiounifi.controller import (
    MESSAGE_CLIENT,
    MESSAGE_CLIENT_REMOVED,
    MESSAGE_DEVICE,
    MESSAGE_EVENT,
)
from aiounifi.websocket import STATE_DISCONNECTED, STATE_RUNNING

from homeassistant import config_entries
from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.unifi.const import (
    CONF_BLOCK_CLIENT,
    CONF_IGNORE_WIRED_BUG,
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.const import STATE_HOME, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from .test_controller import ENTRY_CONFIG, setup_unifi_integration

from tests.common import async_fire_time_changed


async def test_no_entities(hass, aioclient_mock):
    """Test the update_clients function when no clients are found."""
    await setup_unifi_integration(hass, aioclient_mock)

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 0


async def test_tracked_wireless_clients(hass, aioclient_mock, mock_unifi_websocket):
    """Verify tracking of wireless clients."""
    client = {
        "ap_mac": "00:00:00:00:02:01",
        "essid": "ssid",
        "hostname": "client",
        "ip": "10.0.0.1",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_response=[client]
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert hass.states.get("device_tracker.client").state == STATE_NOT_HOME

    # State change signalling works without events

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    await hass.async_block_till_done()

    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == "home"
    assert client_state.attributes["ip"] == "10.0.0.1"
    assert client_state.attributes["mac"] == "00:00:00:00:00:01"
    assert client_state.attributes["hostname"] == "client"
    assert client_state.attributes["host_name"] == "client"

    # State change signalling works with events

    # Disconnected event

    event = {
        "user": client["mac"],
        "ssid": client["essid"],
        "hostname": client["hostname"],
        "ap": client["ap_mac"],
        "duration": 467,
        "bytes": 459039,
        "key": "EVT_WU_Disconnected",
        "subsystem": "wlan",
        "site_id": "name",
        "time": 1587752927000,
        "datetime": "2020-04-24T18:28:47Z",
        "msg": f'User{[client["mac"]]} disconnected from "{client["essid"]}" (7m 47s connected, 448.28K bytes, last AP[{client["ap_mac"]}])',
        "_id": "5ea32ff730c49e00f90dca1a",
    }
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_EVENT},
            "data": [event],
        }
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client").state == STATE_HOME

    # Change time to mark client as away

    new_time = dt_util.utcnow() + controller.option_detection_time
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client").state == STATE_NOT_HOME

    # Connected event

    event = {
        "user": client["mac"],
        "ssid": client["essid"],
        "ap": client["ap_mac"],
        "radio": "na",
        "channel": "44",
        "hostname": client["hostname"],
        "key": "EVT_WU_Connected",
        "subsystem": "wlan",
        "site_id": "name",
        "time": 1587753456179,
        "datetime": "2020-04-24T18:37:36Z",
        "msg": f'User{[client["mac"]]} has connected to AP[{client["ap_mac"]}] with SSID "{client["essid"]}" on "channel 44(na)"',
        "_id": "5ea331fa30c49e00f90ddc1a",
    }
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_EVENT},
            "data": [event],
        }
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client").state == STATE_HOME


async def test_tracked_clients(hass, aioclient_mock, mock_unifi_websocket):
    """Test the update_items function with some clients."""
    client_1 = {
        "ap_mac": "00:00:00:00:02:01",
        "essid": "ssid",
        "hostname": "client_1",
        "ip": "10.0.0.1",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    client_2 = {
        "ip": "10.0.0.2",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
        "name": "Client 2",
    }
    client_3 = {
        "essid": "ssid2",
        "hostname": "client_3",
        "ip": "10.0.0.3",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:03",
    }
    client_4 = {
        "essid": "ssid",
        "hostname": "client_4",
        "ip": "10.0.0.4",
        "is_wired": True,
        "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        "mac": "00:00:00:00:00:04",
    }
    client_5 = {
        "essid": "ssid",
        "hostname": "client_5",
        "ip": "10.0.0.5",
        "is_wired": True,
        "last_seen": None,
        "mac": "00:00:00:00:00:05",
    }

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_SSID_FILTER: ["ssid"]},
        clients_response=[client_1, client_2, client_3, client_4, client_5],
        known_wireless_clients=(client_4["mac"],),
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 4
    assert hass.states.get("device_tracker.client_1").state == STATE_NOT_HOME
    assert hass.states.get("device_tracker.client_2").state == STATE_NOT_HOME

    # Client on SSID not in SSID filter
    assert not hass.states.get("device_tracker.client_3")

    # Wireless client with wired bug, if bug active on restart mark device away
    assert hass.states.get("device_tracker.client_4").state == STATE_NOT_HOME

    # A client that has never been seen should be marked away.
    assert hass.states.get("device_tracker.client_5").state == STATE_NOT_HOME

    # State change signalling works

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client_1],
        }
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client_1").state == STATE_HOME


async def test_tracked_devices(hass, aioclient_mock, mock_unifi_websocket):
    """Test the update_items function with some devices."""
    device_1 = {
        "board_rev": 3,
        "device_id": "mock-id",
        "has_fan": True,
        "fan_level": 0,
        "ip": "10.0.1.1",
        "last_seen": 1562600145,
        "mac": "00:00:00:00:01:01",
        "model": "US16P150",
        "name": "Device 1",
        "next_interval": 20,
        "overheating": True,
        "state": 1,
        "type": "usw",
        "upgradable": True,
        "version": "4.0.42.10433",
    }
    device_2 = {
        "board_rev": 3,
        "device_id": "mock-id",
        "has_fan": True,
        "ip": "10.0.1.2",
        "mac": "00:00:00:00:01:02",
        "model": "US16P150",
        "name": "Device 2",
        "next_interval": 20,
        "state": 0,
        "type": "usw",
        "version": "4.0.42.10433",
    }
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        devices_response=[device_1, device_2],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.device_1").state == STATE_HOME
    assert hass.states.get("device_tracker.device_2").state == STATE_NOT_HOME

    # State change signalling work

    device_1["next_interval"] = 20
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_DEVICE},
            "data": [device_1],
        }
    )
    device_2["next_interval"] = 50
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_DEVICE},
            "data": [device_2],
        }
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.device_1").state == STATE_HOME
    assert hass.states.get("device_tracker.device_2").state == STATE_HOME

    # Change of time can mark device not_home outside of expected reporting interval

    new_time = dt_util.utcnow() + timedelta(seconds=90)
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.device_1").state == STATE_NOT_HOME
    assert hass.states.get("device_tracker.device_2").state == STATE_HOME

    # Disabled device is unavailable

    device_1["disabled"] = True
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_DEVICE},
            "data": [device_1],
        }
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.device_1").state == STATE_UNAVAILABLE
    assert hass.states.get("device_tracker.device_2").state == STATE_HOME

    # Update device registry when device is upgraded

    event = {
        "_id": "5eae7fe02ab79c00f9d38960",
        "datetime": "2020-05-09T20:06:37Z",
        "key": "EVT_SW_Upgraded",
        "msg": f'Switch[{device_2["mac"]}] was upgraded from "{device_2["version"]}" to "4.3.13.11253"',
        "subsystem": "lan",
        "sw": device_2["mac"],
        "sw_name": device_2["name"],
        "time": 1589054797635,
        "version_from": {device_2["version"]},
        "version_to": "4.3.13.11253",
    }

    device_2["version"] = event["version_to"]
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_DEVICE},
            "data": [device_2],
        }
    )
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_EVENT},
            "data": [event],
        }
    )
    await hass.async_block_till_done()

    # Verify device registry has been updated
    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("device_tracker.device_2")
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(entry.device_id)
    assert device.sw_version == event["version_to"]


async def test_remove_clients(hass, aioclient_mock, mock_unifi_websocket):
    """Test the remove_items function with some clients."""
    client_1 = {
        "essid": "ssid",
        "hostname": "client_1",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    client_2 = {
        "hostname": "client_2",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
    }
    await setup_unifi_integration(
        hass, aioclient_mock, clients_response=[client_1, client_2]
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.client_1")
    assert hass.states.get("device_tracker.client_2")

    # Remove client

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT_REMOVED},
            "data": [client_1],
        }
    )
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert not hass.states.get("device_tracker.client_1")
    assert hass.states.get("device_tracker.client_2")


async def test_controller_state_change(hass, aioclient_mock, mock_unifi_websocket):
    """Verify entities state reflect on controller becoming unavailable."""
    client = {
        "essid": "ssid",
        "hostname": "client",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    device = {
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
        "version": "4.0.42.10433",
    }

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        clients_response=[client],
        devices_response=[device],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.client").state == STATE_NOT_HOME
    assert hass.states.get("device_tracker.device").state == STATE_HOME

    # Controller unavailable
    mock_unifi_websocket(state=STATE_DISCONNECTED)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client").state == STATE_UNAVAILABLE
    assert hass.states.get("device_tracker.device").state == STATE_UNAVAILABLE

    # Controller available
    mock_unifi_websocket(state=STATE_RUNNING)
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client").state == STATE_NOT_HOME
    assert hass.states.get("device_tracker.device").state == STATE_HOME


async def test_option_track_clients(hass, aioclient_mock):
    """Test the tracking of clients can be turned off."""
    wireless_client = {
        "essid": "ssid",
        "hostname": "wireless_client",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    wired_client = {
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
        "name": "Wired Client",
    }
    device = {
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
        "version": "4.0.42.10433",
    }

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        clients_response=[wireless_client, wired_client],
        devices_response=[device],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3
    assert hass.states.get("device_tracker.wireless_client")
    assert hass.states.get("device_tracker.wired_client")
    assert hass.states.get("device_tracker.device")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_CLIENTS: False},
    )
    await hass.async_block_till_done()

    assert not hass.states.get("device_tracker.wireless_client")
    assert not hass.states.get("device_tracker.wired_client")
    assert hass.states.get("device_tracker.device")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_CLIENTS: True},
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.wireless_client")
    assert hass.states.get("device_tracker.wired_client")
    assert hass.states.get("device_tracker.device")


async def test_option_track_wired_clients(hass, aioclient_mock):
    """Test the tracking of wired clients can be turned off."""
    wireless_client = {
        "essid": "ssid",
        "hostname": "wireless_client",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    wired_client = {
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
        "name": "Wired Client",
    }
    device = {
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
        "version": "4.0.42.10433",
    }

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        clients_response=[wireless_client, wired_client],
        devices_response=[device],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3
    assert hass.states.get("device_tracker.wireless_client")
    assert hass.states.get("device_tracker.wired_client")
    assert hass.states.get("device_tracker.device")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_WIRED_CLIENTS: False},
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.wireless_client")
    assert not hass.states.get("device_tracker.wired_client")
    assert hass.states.get("device_tracker.device")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_WIRED_CLIENTS: True},
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.wireless_client")
    assert hass.states.get("device_tracker.wired_client")
    assert hass.states.get("device_tracker.device")


async def test_option_track_devices(hass, aioclient_mock):
    """Test the tracking of devices can be turned off."""
    client = {
        "hostname": "client",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    device = {
        "board_rev": 3,
        "device_id": "mock-id",
        "last_seen": 1562600145,
        "mac": "00:00:00:00:01:01",
        "model": "US16P150",
        "name": "Device",
        "next_interval": 20,
        "overheating": True,
        "state": 1,
        "type": "usw",
        "upgradable": True,
        "version": "4.0.42.10433",
    }

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        clients_response=[client],
        devices_response=[device],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.client")
    assert hass.states.get("device_tracker.device")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_DEVICES: False},
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client")
    assert not hass.states.get("device_tracker.device")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_DEVICES: True},
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client")
    assert hass.states.get("device_tracker.device")


async def test_option_ssid_filter(hass, aioclient_mock, mock_unifi_websocket):
    """Test the SSID filter works.

    Client will travel from a supported SSID to an unsupported ssid.
    Client on SSID2 will be removed on change of options.
    """
    client = {
        "essid": "ssid",
        "hostname": "client",
        "is_wired": False,
        "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        "mac": "00:00:00:00:00:01",
    }
    client_on_ssid2 = {
        "essid": "ssid2",
        "hostname": "client_on_ssid2",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
    }

    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_response=[client, client_on_ssid2]
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    assert hass.states.get("device_tracker.client").state == STATE_HOME
    assert hass.states.get("device_tracker.client_on_ssid2").state == STATE_NOT_HOME

    # Setting SSID filter will remove clients outside of filter
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_SSID_FILTER: ["ssid"]},
    )
    await hass.async_block_till_done()

    # Not affected by SSID filter
    assert hass.states.get("device_tracker.client").state == STATE_HOME

    # Removed due to SSID filter
    assert not hass.states.get("device_tracker.client_on_ssid2")

    # Roams to SSID outside of filter
    client["essid"] = "other_ssid"
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    # Data update while SSID filter is in effect shouldn't create the client
    client_on_ssid2["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client_on_ssid2],
        }
    )
    await hass.async_block_till_done()

    # SSID filter marks client as away
    assert hass.states.get("device_tracker.client").state == STATE_NOT_HOME

    # SSID still outside of filter
    assert not hass.states.get("device_tracker.client_on_ssid2")

    # Remove SSID filter
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_SSID_FILTER: []},
    )
    await hass.async_block_till_done()

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client_on_ssid2],
        }
    )
    await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client").state == STATE_HOME
    assert hass.states.get("device_tracker.client_on_ssid2").state == STATE_HOME

    # Time pass to mark client as away

    new_time = dt_util.utcnow() + controller.option_detection_time
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client").state == STATE_NOT_HOME

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client_on_ssid2],
        }
    )
    await hass.async_block_till_done()

    # Client won't go away until after next update
    assert hass.states.get("device_tracker.client_on_ssid2").state == STATE_HOME

    # Trigger update to get client marked as away
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client_on_ssid2],
        }
    )
    await hass.async_block_till_done()

    new_time = (
        dt_util.utcnow() + controller.option_detection_time + timedelta(seconds=1)
    )
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    assert hass.states.get("device_tracker.client_on_ssid2").state == STATE_NOT_HOME


async def test_wireless_client_go_wired_issue(
    hass, aioclient_mock, mock_unifi_websocket
):
    """Test the solution to catch wireless device go wired UniFi issue.

    UniFi has a known issue that when a wireless device goes away it sometimes gets marked as wired.
    """
    client = {
        "essid": "ssid",
        "hostname": "client",
        "ip": "10.0.0.1",
        "is_wired": False,
        "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        "mac": "00:00:00:00:00:01",
    }

    config_entry = await setup_unifi_integration(
        hass, aioclient_mock, clients_response=[client]
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    # Client is wireless
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_HOME
    assert client_state.attributes["is_wired"] is False

    # Trigger wired bug
    client["is_wired"] = True
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    await hass.async_block_till_done()

    # Wired bug fix keeps client marked as wireless
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_HOME
    assert client_state.attributes["is_wired"] is False

    # Pass time
    new_time = dt_util.utcnow() + controller.option_detection_time
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    # Marked as home according to the timer
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_NOT_HOME
    assert client_state.attributes["is_wired"] is False

    # Try to mark client as connected
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    await hass.async_block_till_done()

    # Make sure it don't go online again until wired bug disappears
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_NOT_HOME
    assert client_state.attributes["is_wired"] is False

    # Make client wireless
    client["is_wired"] = False
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    await hass.async_block_till_done()

    # Client is no longer affected by wired bug and can be marked online
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_HOME
    assert client_state.attributes["is_wired"] is False


async def test_option_ignore_wired_bug(hass, aioclient_mock, mock_unifi_websocket):
    """Test option to ignore wired bug."""
    client = {
        "ap_mac": "00:00:00:00:02:01",
        "essid": "ssid",
        "hostname": "client",
        "ip": "10.0.0.1",
        "is_wired": False,
        "last_seen": dt_util.as_timestamp(dt_util.utcnow()),
        "mac": "00:00:00:00:00:01",
    }

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_IGNORE_WIRED_BUG: True},
        clients_response=[client],
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    # Client is wireless
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_HOME
    assert client_state.attributes["is_wired"] is False

    # Trigger wired bug
    client["is_wired"] = True
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    await hass.async_block_till_done()

    # Wired bug in effect
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_HOME
    assert client_state.attributes["is_wired"] is True

    # pass time
    new_time = dt_util.utcnow() + controller.option_detection_time
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    # Timer marks client as away
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_NOT_HOME
    assert client_state.attributes["is_wired"] is True

    # Mark client as connected again
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    await hass.async_block_till_done()

    # Ignoring wired bug allows client to go home again even while affected
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_HOME
    assert client_state.attributes["is_wired"] is True

    # Make client wireless
    client["is_wired"] = False
    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT},
            "data": [client],
        }
    )
    await hass.async_block_till_done()

    # Client is wireless and still connected
    client_state = hass.states.get("device_tracker.client")
    assert client_state.state == STATE_HOME
    assert client_state.attributes["is_wired"] is False


async def test_restoring_client(hass, aioclient_mock):
    """Verify clients are restored from clients_all if they ever was registered to entity registry."""
    client = {
        "hostname": "client",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    restored = {
        "hostname": "restored",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
    }
    not_restored = {
        "hostname": "not_restored",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:03",
    }

    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=UNIFI_DOMAIN,
        title="Mock Title",
        data=ENTRY_CONFIG,
        source="test",
        system_options={},
        options={},
        entry_id=1,
    )

    registry = er.async_get(hass)
    registry.async_get_or_create(
        TRACKER_DOMAIN,
        UNIFI_DOMAIN,
        f'{restored["mac"]}-site_id',
        suggested_object_id=restored["hostname"],
        config_entry=config_entry,
    )

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_BLOCK_CLIENT: True},
        clients_response=[client],
        clients_all_response=[restored, not_restored],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.client")
    assert hass.states.get("device_tracker.restored")
    assert not hass.states.get("device_tracker.not_restored")


async def test_dont_track_clients(hass, aioclient_mock):
    """Test don't track clients config works."""
    wireless_client = {
        "essid": "ssid",
        "hostname": "Wireless client",
        "ip": "10.0.0.1",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    wired_client = {
        "hostname": "Wired client",
        "ip": "10.0.0.2",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
    }
    device = {
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
        "version": "4.0.42.10433",
    }

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_TRACK_CLIENTS: False},
        clients_response=[wireless_client, wired_client],
        devices_response=[device],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert not hass.states.get("device_tracker.wireless_client")
    assert not hass.states.get("device_tracker.wired_client")
    assert hass.states.get("device_tracker.device")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_CLIENTS: True},
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3
    assert hass.states.get("device_tracker.wireless_client")
    assert hass.states.get("device_tracker.wired_client")
    assert hass.states.get("device_tracker.device")


async def test_dont_track_devices(hass, aioclient_mock):
    """Test don't track devices config works."""
    client = {
        "hostname": "client",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    device = {
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
        "version": "4.0.42.10433",
    }

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_TRACK_DEVICES: False},
        clients_response=[client],
        devices_response=[device],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert hass.states.get("device_tracker.client")
    assert not hass.states.get("device_tracker.device")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_DEVICES: True},
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.client")
    assert hass.states.get("device_tracker.device")


async def test_dont_track_wired_clients(hass, aioclient_mock):
    """Test don't track wired clients config works."""
    wireless_client = {
        "essid": "ssid",
        "hostname": "Wireless Client",
        "is_wired": False,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
    }
    wired_client = {
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:02",
        "name": "Wired Client",
    }

    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_TRACK_WIRED_CLIENTS: False},
        clients_response=[wireless_client, wired_client],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1
    assert hass.states.get("device_tracker.wireless_client")
    assert not hass.states.get("device_tracker.wired_client")

    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_TRACK_WIRED_CLIENTS: True},
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2
    assert hass.states.get("device_tracker.wireless_client")
    assert hass.states.get("device_tracker.wired_client")
