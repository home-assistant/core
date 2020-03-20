"""The tests for the UniFi device tracker platform."""
from copy import copy
from datetime import timedelta

from aiounifi.controller import SIGNAL_CONNECTION_STATE
from aiounifi.websocket import STATE_DISCONNECTED, STATE_RUNNING
from asynctest import patch

from homeassistant import config_entries
from homeassistant.components import unifi
import homeassistant.components.device_tracker as device_tracker
from homeassistant.components.unifi.const import (
    CONF_SSID_FILTER,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    CONF_TRACK_WIRED_CLIENTS,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .test_controller import ENTRY_CONFIG, setup_unifi_integration

CLIENT_1 = {
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
    "ip": "10.0.1.1",
    "mac": "00:00:00:00:01:01",
    "model": "US16P150",
    "name": "device_1",
    "state": 0,
    "type": "usw",
    "version": "4.0.42.10433",
}


async def test_platform_manually_configured(hass):
    """Test that nothing happens when configuring unifi through device tracker platform."""
    assert (
        await async_setup_component(
            hass, device_tracker.DOMAIN, {device_tracker.DOMAIN: {"platform": "unifi"}}
        )
        is False
    )
    assert unifi.DOMAIN not in hass.data


async def test_no_clients(hass):
    """Test the update_clients function when no clients are found."""
    await setup_unifi_integration(hass)

    assert len(hass.states.async_entity_ids("device_tracker")) == 0


async def test_tracked_devices(hass):
    """Test the update_items function with some clients."""
    client_4_copy = copy(CLIENT_4)
    client_4_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())

    controller = await setup_unifi_integration(
        hass,
        options={CONF_SSID_FILTER: ["ssid"]},
        clients_response=[CLIENT_1, CLIENT_2, CLIENT_3, CLIENT_5, client_4_copy],
        devices_response=[DEVICE_1, DEVICE_2],
        known_wireless_clients=(CLIENT_4["mac"],),
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 6

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "not_home"

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None
    assert client_2.state == "not_home"

    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3 is not None
    assert client_3.state == "not_home"

    # Wireless client with wired bug, if bug active on restart mark device away
    client_4 = hass.states.get("device_tracker.client_4")
    assert client_4 is not None
    assert client_4.state == "not_home"

    # A client that has never been seen should be marked away.
    client_5 = hass.states.get("device_tracker.client_5")
    assert client_5 is not None
    assert client_5.state == "not_home"

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "not_home"

    # State change signalling works
    client_1_copy = copy(CLIENT_1)
    client_1_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    event = {"meta": {"message": "sta:sync"}, "data": [client_1_copy]}
    controller.api.message_handler(event)
    device_1_copy = copy(DEVICE_1)
    device_1_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    event = {"meta": {"message": "device:sync"}, "data": [device_1_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == "home"

    # Disabled device is unavailable
    device_1_copy = copy(DEVICE_1)
    device_1_copy["disabled"] = True
    event = {"meta": {"message": "device:sync"}, "data": [device_1_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1.state == STATE_UNAVAILABLE


async def test_controller_state_change(hass):
    """Verify entities state reflect on controller becoming unavailable."""
    controller = await setup_unifi_integration(
        hass, clients_response=[CLIENT_1], devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 2

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
    assert device_1.state == "not_home"


async def test_option_track_clients(hass):
    """Test the tracking of clients can be turned off."""
    controller = await setup_unifi_integration(
        hass, clients_response=[CLIENT_1, CLIENT_2], devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry, options={CONF_TRACK_CLIENTS: False},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry, options={CONF_TRACK_CLIENTS: True},
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
        hass, clients_response=[CLIENT_1, CLIENT_2], devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry, options={CONF_TRACK_WIRED_CLIENTS: False},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry, options={CONF_TRACK_WIRED_CLIENTS: True},
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
        hass, clients_response=[CLIENT_1, CLIENT_2], devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 3

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None

    hass.config_entries.async_update_entry(
        controller.config_entry, options={CONF_TRACK_DEVICES: False},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is None

    hass.config_entries.async_update_entry(
        controller.config_entry, options={CONF_TRACK_DEVICES: True},
    )
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None

    client_2 = hass.states.get("device_tracker.wired_client")
    assert client_2 is not None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None


async def test_option_ssid_filter(hass):
    """Test the SSID filter works."""
    controller = await setup_unifi_integration(
        hass, options={CONF_SSID_FILTER: ["ssid"]}, clients_response=[CLIENT_3],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 1

    # SSID filter active
    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3.state == "not_home"

    client_3_copy = copy(CLIENT_3)
    client_3_copy["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    event = {"meta": {"message": "sta:sync"}, "data": [client_3_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # SSID filter active even though time stamp should mark as home
    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3.state == "not_home"

    # Remove SSID filter
    hass.config_entries.async_update_entry(
        controller.config_entry, options={CONF_SSID_FILTER: []},
    )
    event = {"meta": {"message": "sta:sync"}, "data": [client_3_copy]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    # SSID no longer filtered
    client_3 = hass.states.get("device_tracker.client_3")
    assert client_3.state == "home"


async def test_wireless_client_go_wired_issue(hass):
    """Test the solution to catch wireless device go wired UniFi issue.

    UniFi has a known issue that when a wireless device goes away it sometimes gets marked as wired.
    """
    client_1_client = copy(CLIENT_1)
    client_1_client["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())

    controller = await setup_unifi_integration(hass, clients_response=[client_1_client])
    assert len(hass.states.async_entity_ids("device_tracker")) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "home"

    client_1_client["is_wired"] = True
    client_1_client["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    event = {"meta": {"message": "sta:sync"}, "data": [client_1_client]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"

    with patch.object(
        unifi.device_tracker.dt_util,
        "utcnow",
        return_value=(dt_util.utcnow() + timedelta(minutes=5)),
    ):
        event = {"meta": {"message": "sta:sync"}, "data": [client_1_client]}
        controller.api.message_handler(event)
        await hass.async_block_till_done()

        client_1 = hass.states.get("device_tracker.client_1")
        assert client_1.state == "not_home"

    client_1_client["is_wired"] = False
    client_1_client["last_seen"] = dt_util.as_timestamp(dt_util.utcnow())
    event = {"meta": {"message": "sta:sync"}, "data": [client_1_client]}
    controller.api.message_handler(event)
    await hass.async_block_till_done()

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1.state == "home"


async def test_restoring_client(hass):
    """Test the update_items function with some clients."""
    config_entry = config_entries.ConfigEntry(
        version=1,
        domain=unifi.DOMAIN,
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
        device_tracker.DOMAIN,
        unifi.DOMAIN,
        "{}-site_id".format(CLIENT_1["mac"]),
        suggested_object_id=CLIENT_1["hostname"],
        config_entry=config_entry,
    )
    registry.async_get_or_create(
        device_tracker.DOMAIN,
        unifi.DOMAIN,
        "{}-site_id".format(CLIENT_2["mac"]),
        suggested_object_id=CLIENT_2["hostname"],
        config_entry=config_entry,
    )

    await setup_unifi_integration(
        hass,
        options={unifi.CONF_BLOCK_CLIENT: True},
        clients_response=[CLIENT_2],
        clients_all_response=[CLIENT_1],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 2

    device_1 = hass.states.get("device_tracker.client_1")
    assert device_1 is not None


async def test_dont_track_clients(hass):
    """Test don't track clients config works."""
    await setup_unifi_integration(
        hass,
        options={unifi.controller.CONF_TRACK_CLIENTS: False},
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is None

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is not None
    assert device_1.state == "not_home"


async def test_dont_track_devices(hass):
    """Test don't track devices config works."""
    await setup_unifi_integration(
        hass,
        options={unifi.controller.CONF_TRACK_DEVICES: False},
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "not_home"

    device_1 = hass.states.get("device_tracker.device_1")
    assert device_1 is None


async def test_dont_track_wired_clients(hass):
    """Test don't track wired clients config works."""
    await setup_unifi_integration(
        hass,
        options={unifi.controller.CONF_TRACK_WIRED_CLIENTS: False},
        clients_response=[CLIENT_1, CLIENT_2],
    )
    assert len(hass.states.async_entity_ids("device_tracker")) == 1

    client_1 = hass.states.get("device_tracker.client_1")
    assert client_1 is not None
    assert client_1.state == "not_home"

    client_2 = hass.states.get("device_tracker.client_2")
    assert client_2 is None
