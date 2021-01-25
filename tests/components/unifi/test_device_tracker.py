"""The tests for the UniFi device tracker platform."""
from copy import copy
from datetime import timedelta
from unittest.mock import patch

from aiounifi.controller import (
    MESSAGE_CLIENT,
    MESSAGE_CLIENT_REMOVED,
    MESSAGE_DEVICE,
    MESSAGE_EVENT,
    SIGNAL_CONNECTION_STATE,
)
from aiounifi.websocket import SIGNAL_DATA, STATE_DISCONNECTED, STATE_RUNNING

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
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .test_controller import ENTRY_CONFIG, setup_unifi_integration

from tests.common import async_fire_time_changed

CLIENT_1 = {
    "ap_mac": "00:00:00:00:02:01",
    "essid": "ssid",
    "hostname": "client_1",
    "ip": "10.0.0.1",
    "is_wired": False,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:01",
}
CLIENT_2 = {
    "hostname": "client_2",
    "ip": "10.0.0.2",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:02",
    "name": "Wired Client",
}
CLIENT_3 = {
    "essid": "ssid2",
    "hostname": "client_3",
    "ip": "10.0.0.3",
    "is_wired": False,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:03",
}
CLIENT_4 = {
    "essid": "ssid",
    "hostname": "client_4",
    "ip": "10.0.0.4",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:04",
}
CLIENT_5 = {
    "essid": "ssid",
    "hostname": "client_5",
    "ip": "10.0.0.5",
    "is_wired": True,
    "last_seen": None,
    "mac": "00:00:00:00:00:05",
}

DEVICE_1 = {
    "board_rev": 3,
    "device_id": "mock-id",
    "has_fan": True,
    "fan_level": 0,
    "ip": "10.0.1.1",
    "last_seen": 1562600145,
    "mac": "00:00:00:00:01:01",
    "model": "US16P150",
    "name": "device_1",
    "next_interval": 20,
    "overheating": True,
    "state": 1,
    "type": "usw",
    "upgradable": True,
    "version": "4.0.42.10433",
}
DEVICE_2 = {
    "board_rev": 3,
    "device_id": "mock-id",
    "has_fan": True,
    "ip": "10.0.1.2",
    "mac": "00:00:00:00:01:02",
    "model": "US16P150",
    "name": "device_2",
    "next_interval": 20,
    "state": 0,
    "type": "usw",
    "version": "4.0.42.10433",
}

EVENT_CLIENT_1_WIRELESS_CONNECTED = {
    "user": CLIENT_1["mac"],
    "ssid": CLIENT_1["essid"],
    "ap": CLIENT_1["ap_mac"],
    "radio": "na",
    "channel": "44",
    "hostname": CLIENT_1["hostname"],
    "key": "EVT_WU_Connected",
    "subsystem": "wlan",
    "site_id": "name",
    "time": 1587753456179,
    "datetime": "2020-04-24T18:37:36Z",
    "msg": f'User{[CLIENT_1["mac"]]} has connected to AP[{CLIENT_1["ap_mac"]}] with SSID "{CLIENT_1["essid"]}" on "channel 44(na)"',
    "_id": "5ea331fa30c49e00f90ddc1a",
}

EVENT_CLIENT_1_WIRELESS_DISCONNECTED = {
    "user": CLIENT_1["mac"],
    "ssid": CLIENT_1["essid"],
    "hostname": CLIENT_1["hostname"],
    "ap": CLIENT_1["ap_mac"],
    "duration": 467,
    "bytes": 459039,
    "key": "EVT_WU_Disconnected",
    "subsystem": "wlan",
    "site_id": "name",
    "time": 1587752927000,
    "datetime": "2020-04-24T18:28:47Z",
    "msg": f'User{[CLIENT_1["mac"]]} disconnected from "{CLIENT_1["essid"]}" (7m 47s connected, 448.28K bytes, last AP[{CLIENT_1["ap_mac"]}])',
    "_id": "5ea32ff730c49e00f90dca1a",
}

EVENT_DEVICE_2_UPGRADED = {
    "_id": "5eae7fe02ab79c00f9d38960",
    "datetime": "2020-05-09T20:06:37Z",
    "key": "EVT_SW_Upgraded",
    "msg": f'Switch[{DEVICE_2["mac"]}] was upgraded from "{DEVICE_2["version"]}" to "4.3.13.11253"',
    "subsystem": "lan",
    "sw": DEVICE_2["mac"],
    "sw_name": DEVICE_2["name"],
    "time": 1589054797635,
    "version_from": {DEVICE_2["version"]},
    "version_to": "4.3.13.11253",
}


async def test_platform_manually_configured(hass):
    """Test that nothing happens when configuring unifi through device tracker platform."""
    assert (
        await async_setup_component(
            hass, TRACKER_DOMAIN, {TRACKER_DOMAIN: {"platform": UNIFI_DOMAIN}}
        )
        is False
    )
    assert UNIFI_DOMAIN not in hass.data


async def test_no_clients(hass):
    """Test the update_clients function when no clients are found."""
    await setup_unifi_integration(hass)

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 0


async def test_tracked_wireless_clients(hass):
    """Test the update_items function with some clients."""
    controller = await setup_unifi_integration(hass, clients_response=[CLIENT_1])
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "not_home"

    # State change signalling works without events
    client_1_copy = copy(CLIENT_1)
    controller.api.websocket._data = {
        "meta": {"message": MESSAGE_CLIENT},
        "data": [client_1_copy],
    }
    controller.api.session_handler(SIGNAL_DATA)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"
    assert client_1.attributes["ip"] == "10.0.0.1"
    assert client_1.attributes["mac"] == "00:00:00:00:00:01"
    assert client_1.attributes["hostname"] == "client_1"
    assert client_1.attributes["host_name"] == "client_1"

    # State change signalling works with events
    controller.api.websocket._data = {
        "meta": {"message": MESSAGE_EVENT},
        "data": [EVENT_CLIENT_1_WIRELESS_DISCONNECTED],
    }
    controller.api.session_handler(SIGNAL_DATA)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"

    new_time = dt_util.utcnow() + controller.option_detection_time
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "not_home"

    controller.api.websocket._data = {
        "meta": {"message": MESSAGE_EVENT},
        "data": [EVENT_CLIENT_1_WIRELESS_CONNECTED],
    }
    controller.api.session_handler(SIGNAL_DATA)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"


async def test_tracked_clients(hass):
    """Test the update_items function with some clients."""
    client_4_copy = copy(CLIENT_4)
    client_4_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())

    controller = await setup_unifi_integration(
        hass,
        options={CONF_SSID_FILTER: ["ssid"]},
        clients_response=[CLIENT_1, CLIENT_2, CLIENT_3, CLIENT_5, client_4_copy],
        known_wireless_clients=(CLIENT_4["mac"],),
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 4

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "not_home"

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None
    assert client_2.state == "not_home"

    # Client on SSID not in SSID filter
    client_3 = hass.states.get("device_tracker.client_3")
    assert not client_3

    # Wireless client with wired bug, if bug active on restart mark device away
    client_4 = hass.states.get("device_tracker.client_4")
    assert client_4 is not None
    assert client_4.state == "not_home"

    # A client that has never been seen should be marked away.
    client_5 = hass.states.get("device_tracker.client_5")
    assert client_5 is not None
    assert client_5.state == "not_home"

    # State change signalling works
    client_1_copy = copy(CLIENT_1)
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"


async def test_tracked_devices(hass):
    """Test the update_items function with some devices."""
    controller = await setup_unifi_integration(
        hass,
        devices_response=[DEVICE_1, DEVICE_2],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1
    assert device_1.state == "home"

    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2
    assert device_2.state == "not_home"

    # State change signalling work
    device_1_copy = copy(DEVICE_1)
    device_1_copy["next_interval"] = 20
    event = {"meta": {"message": MESSAGE_DEVICE}, "data": [device_1_copy]}
    controller.api.message_handler(event)
    device_2_copy = copy(DEVICE_2)
    device_2_copy["next_interval"] = 50
    event = {"meta": {"message": MESSAGE_DEVICE}, "data": [device_2_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == "home"
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2.state == "home"

    new_time = dt_util.utcnow() + timedelta(seconds=90)
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == "not_home"
    device_2 = hass.states.get("device_tracker.device_2")
    assert device_2.state == "home"

    # Disabled device is unavailable
    device_1_copy = copy(DEVICE_1)
    device_1_copy["disabled"] = True
    event = {"meta": {"message": MESSAGE_DEVICE}, "data": [device_1_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == STATE_UNAVAILABLE

    # Update device registry when device is upgraded
    device_2_copy = copy(DEVICE_2)
    device_2_copy["version"] = EVENT_DEVICE_2_UPGRADED["version_to"]
    message = {"meta": {"message": MESSAGE_DEVICE}, "data": [device_2_copy]}
    controller.api.message_handler(message)
    event = {"meta": {"message": MESSAGE_EVENT}, "data": [EVENT_DEVICE_2_UPGRADED]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # Verify device registry has been updated
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry = entity_registry.async_get("device_tracker.device_2")
    device_registry = await hass.helpers.device_registry.async_get_registry()
    device = device_registry.async_get(entry.device_id)
    assert device.sw_version == EVENT_DEVICE_2_UPGRADED["version_to"]


async def test_remove_clients(hass):
    """Test the remove_items function with some clients."""
    controller = await setup_unifi_integration(
        hass, clients_response=[CLIENT_1, CLIENT_2]
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    wired_client = hass.states.get("device_tracker.wired_client")
    assert wired_client is not None

    controller.api.websocket._data = {
        "meta": {"message": MESSAGE_CLIENT_REMOVED},
        "data": [CLIENT_1],
    }
    controller.api.session_handler(SIGNAL_DATA)
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is None

    wired_client = hass.states.get("device_tracker.wired_client")
    assert wired_client is not None


async def test_controller_state_change(hass):
    """Verify entities state reflect on controller becoming unavailable."""
    controller = await setup_unifi_integration(
        hass,
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "not_home"

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == "home"

    # Controller unavailable
    controller.async_unifi_signalling_callback(
        SIGNAL_CONNECTION_STATE, STATE_DISCONNECTED
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == STATE_UNAVAILABLE

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == STATE_UNAVAILABLE

    # Controller available
    controller.async_unifi_signalling_callback(SIGNAL_CONNECTION_STATE, STATE_RUNNING)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "not_home"

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == "home"


async def test_option_track_clients(hass):
    """Test the tracking of clients can be turned off."""
    controller = await setup_unifi_integration(
        hass,
        clients_response=[CLIENT_1, CLIENT_2],
        devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_CLIENTS: False},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_CLIENTS: True},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None


async def test_option_track_wired_clients(hass):
    """Test the tracking of wired clients can be turned off."""
    controller = await setup_unifi_integration(
        hass,
        clients_response=[CLIENT_1, CLIENT_2],
        devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_WIRED_CLIENTS: False},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_WIRED_CLIENTS: True},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None


async def test_option_track_devices(hass):
    """Test the tracking of devices can be turned off."""
    controller = await setup_unifi_integration(
        hass,
        clients_response=[CLIENT_1, CLIENT_2],
        devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_DEVICES: False},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_DEVICES: True},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None


async def test_option_ssid_filter(hass):
    """Test the SSID filter works.

    Client 1 will travel from a supported SSID to an unsupported ssid.
    Client 3 will be removed on change of options since it is in an unsupported SSID.
    """
    client_1_copy = copy(CLIENT_1)
    client_1_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())

    controller = await setup_unifi_integration(
        hass, clients_response=[client_1_copy, CLIENT_3]
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"

    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3

    # Setting SSID filter will remove clients outside of filter
    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_SSID_FILTER: ["ssid"]},
    )
    await hass.async_block_till_done()

    # Not affected by SSID filter
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"

    # Removed due to SSID filter
    client_3 = hass.states.get("device_tracker.client_3")
    assert not client_3

    # Roams to SSID outside of filter
    client_1_copy = copy(CLIENT_1)
    client_1_copy["essid"] = "other_ssid"
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_copy]}
    controller.api.message_handler(event)
    # Data update while SSID filter is in effect shouldn't create the client
    client_3_copy = copy(CLIENT_3)
    client_3_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_3_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # SSID filter marks client as away
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "not_home"

    # SSID still outside of filter
    client_3 = hass.states.get("device_tracker.client_3")
    assert not client_3

    # Remove SSID filter
    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_SSID_FILTER: []},
    )
    await hass.async_block_till_done()
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_copy]}
    controller.api.message_handler(event)
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_3_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"

    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3.state == "home"

    new_time = dt_util.utcnow() + controller.option_detection_time
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "not_home"

    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_3_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()
    # Client won't go away until after next update
    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3.state == "home"

    # Trigger update to get client marked as away
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [CLIENT_3]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    new_time = (
        dt_util.utcnow() + controller.option_detection_time + timedelta(seconds=1)
    )
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3.state == "not_home"


async def test_wireless_client_go_wired_issue(hass):
    """Test the solution to catch wireless device go wired UniFi issue.

    UniFi has a known issue that when a wireless device goes away it sometimes gets marked as wired.
    """
    client_1_client = copy(CLIENT_1)
    client_1_client["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())

    controller = await setup_unifi_integration(hass, clients_response=[client_1_client])
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    # Client is wireless
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "home"
    assert client_1.attributes["is_wired"] is False

    # Trigger wired bug
    client_1_client["is_wired"] = True
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_client]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # Wired bug fix keeps client marked as wireless
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"
    assert client_1.attributes["is_wired"] is False

    # Pass time
    new_time = dt_util.utcnow() + controller.option_detection_time
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    # Marked as home according to the timer
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "not_home"
    assert client_1.attributes["is_wired"] is False

    # Try to mark client as connected
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_client]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # Make sure it don't go online again until wired bug disappears
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "not_home"
    assert client_1.attributes["is_wired"] is False

    # Make client wireless
    client_1_client["is_wired"] = False
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_client]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # Client is no longer affected by wired bug and can be marked online
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"
    assert client_1.attributes["is_wired"] is False


async def test_option_ignore_wired_bug(hass):
    """Test option to ignore wired bug."""
    client_1_client = copy(CLIENT_1)
    client_1_client["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())

    controller = await setup_unifi_integration(
        hass, options={CONF_IGNORE_WIRED_BUG: True}, clients_response=[client_1_client]
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    # Client is wireless
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "home"
    assert client_1.attributes["is_wired"] is False

    # Trigger wired bug
    client_1_client["is_wired"] = True
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_client]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # Wired bug in effect
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"
    assert client_1.attributes["is_wired"] is True

    # pass time
    new_time = dt_util.utcnow() + controller.option_detection_time
    with patch("homeassistant.util.dt.utcnow", return_value=new_time):
        async_fire_time_changed(hass, new_time)
        await hass.async_block_till_done()

    # Timer marks client as away
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "not_home"
    assert client_1.attributes["is_wired"] is True

    # Mark client as connected again
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_client]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # Ignoring wired bug allows client to go home again even while affected
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"
    assert client_1.attributes["is_wired"] is True

    # Make client wireless
    client_1_client["is_wired"] = False
    event = {"meta": {"message": MESSAGE_CLIENT}, "data": [client_1_client]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # Client is wireless and still connected
    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"
    assert client_1.attributes["is_wired"] is False


async def test_restoring_client(hass):
    """Test the update_items function with some clients."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=UNIFI_DOMAIN,
        title="Mock Title",
        data=ENTRY_CONFIG,
        source="test",
        connection_class=config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
        options={},
        entry_id=1,
    )

    registry = await entity_registry.async_get_registry(hass)
    registry.async_get_or_create(
        TRACKER_DOMAIN,
        UNIFI_DOMAIN,
        f'{CLIENT_1["mac"]}-site_id',
        suggested_object_id=CLIENT_1["hostname"],
        config_entry=config_entry,
    )
    registry.async_get_or_create(
        TRACKER_DOMAIN,
        UNIFI_DOMAIN,
        f'{CLIENT_2["mac"]}-site_id',
        suggested_object_id=CLIENT_2["hostname"],
        config_entry=config_entry,
    )

    await setup_unifi_integration(
        hass,
        options={CONF_BLOCK_CLIENT: True},
        clients_response=[CLIENT_2],
        clients_all_response=[CLIENT_1],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    device_1 = hass.states.get("device_tracker.client_1")
    assert device_1 is not None


async def test_dont_track_clients(hass):
    """Test don't track clients config works."""
    controller = await setup_unifi_integration(
        hass,
        options={CONF_TRACK_CLIENTS: False},
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_CLIENTS: True},
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None


async def test_dont_track_devices(hass):
    """Test don't track devices config works."""
    controller = await setup_unifi_integration(
        hass,
        options={CONF_TRACK_DEVICES: False},
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_DEVICES: True},
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None


async def test_dont_track_wired_clients(hass):
    """Test don't track wired clients config works."""
    controller = await setup_unifi_integration(
        hass,
        options={CONF_TRACK_WIRED_CLIENTS: False},
        clients_response=[CLIENT_1, CLIENT_2],
    )
    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is None

    hass.config_entries.async_update_entry(
        controller.config_entry,
        options={CONF_TRACK_WIRED_CLIENTS: True},
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 2

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None
