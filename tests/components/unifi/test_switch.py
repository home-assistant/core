"""UniFi switch platform tests."""
from copy import deepcopy
from unittest.mock import patch

from aiounifi.controller import MESSAGE_CLIENT_REMOVED, MESSAGE_EVENT

from homeassistant import config_entries, core
from homeassistant.components.device_tracker import DOMAIN as TRACKER_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.unifi.const import (
    CONF_BLOCK_CLIENT,
    CONF_DPI_RESTRICTIONS,
    CONF_POE_CLIENTS,
    CONF_TRACK_CLIENTS,
    CONF_TRACK_DEVICES,
    DOMAIN as UNIFI_DOMAIN,
)
from homeassistant.components.unifi.switch import POE_SWITCH
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .test_controller import (
    CONTROLLER_HOST,
    DESCRIPTION,
    ENTRY_CONFIG,
    setup_unifi_integration,
)

CLIENT_1 = {
    "hostname": "client_1",
    "ip": "10.0.0.1",
    "is_wired": True,
    "last_seen": 1562600145,
    "mac": "00:00:00:00:00:01",
    "name": "POE Client 1",
    "oui": "Producer",
    "sw_mac": "00:00:00:00:01:01",
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
    "sw_mac": "00:00:00:00:01:01",
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
    "sw_mac": "00:00:00:00:01:01",
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
    "sw_mac": "00:00:00:00:01:01",
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
        "sw_mac": "00:00:00:00:01:01",
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
        "sw_mac": "00:00:00:00:01:01",
        "sw_port": 1,
        "wired-rx_bytes": 1234000000,
        "wired-tx_bytes": 5678000000,
    },
]

DEVICE_1 = {
    "device_id": "mock-id",
    "ip": "10.0.1.1",
    "mac": "00:00:00:00:01:01",
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


async def test_no_clients(hass, aioclient_mock):
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


async def test_controller_not_client(hass, aioclient_mock):
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


async def test_not_admin(hass, aioclient_mock):
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


async def test_switches(hass, aioclient_mock):
    """Test the update_items function with some clients."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_BLOCK_CLIENT: [BLOCKED["mac"], UNBLOCKED["mac"]],
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        },
        clients_response=[CLIENT_1, CLIENT_4],
        devices_response=[DEVICE_1],
        clients_all_response=[BLOCKED, UNBLOCKED, CLIENT_1],
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=DPI_APPS,
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 4

    switch_1 = hass.states.get("switch.poe_client_1")
    assert switch_1 is not None
    assert switch_1.state == "on"
    assert switch_1.attributes["power"] == "2.56"
    assert switch_1.attributes[SWITCH_DOMAIN] == "00:00:00:00:01:01"
    assert switch_1.attributes["port"] == 1
    assert switch_1.attributes["poe_mode"] == "auto"

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
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 4


async def test_remove_switches(hass, aioclient_mock, mock_unifi_websocket):
    """Test the update_items function with some clients."""
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_BLOCK_CLIENT: [UNBLOCKED["mac"]]},
        clients_response=[CLIENT_1, UNBLOCKED],
        devices_response=[DEVICE_1],
    )

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    poe_switch = hass.states.get("switch.poe_client_1")
    assert poe_switch is not None

    block_switch = hass.states.get("switch.block_client_2")
    assert block_switch is not None

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_CLIENT_REMOVED},
            "data": [CLIENT_1, UNBLOCKED],
        }
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0

    poe_switch = hass.states.get("switch.poe_client_1")
    assert poe_switch is None

    block_switch = hass.states.get("switch.block_client_2")
    assert block_switch is None


async def test_block_switches(hass, aioclient_mock, mock_unifi_websocket):
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

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_EVENT},
            "data": [EVENT_BLOCKED_CLIENT_UNBLOCKED],
        }
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None
    assert blocked.state == "on"

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_EVENT},
            "data": [EVENT_BLOCKED_CLIENT_BLOCKED],
        }
    )
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


async def test_new_client_discovered_on_block_control(
    hass, aioclient_mock, mock_unifi_websocket
):
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

    blocked = hass.states.get("switch.block_client_1")
    assert blocked is None

    mock_unifi_websocket(
        data={
            "meta": {"message": "sta:sync"},
            "data": [BLOCKED],
        }
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_EVENT},
            "data": [EVENT_BLOCKED_CLIENT_CONNECTED],
        }
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1
    blocked = hass.states.get("switch.block_client_1")
    assert blocked is not None


async def test_option_block_clients(hass, aioclient_mock):
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


async def test_option_remove_switches(hass, aioclient_mock):
    """Test removal of DPI switch when options updated."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        },
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
        dpigroup_response=DPI_GROUPS,
        dpiapp_response=DPI_APPS,
    )
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2

    # Disable DPI Switches
    hass.config_entries.async_update_entry(
        config_entry,
        options={CONF_DPI_RESTRICTIONS: False, CONF_POE_CLIENTS: False},
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 0


async def test_new_client_discovered_on_poe_control(
    hass, aioclient_mock, mock_unifi_websocket
):
    """Test if 2nd update has a new client."""
    config_entry = await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={CONF_TRACK_CLIENTS: False, CONF_TRACK_DEVICES: False},
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    mock_unifi_websocket(
        data={
            "meta": {"message": "sta:sync"},
            "data": [CLIENT_2],
        }
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    mock_unifi_websocket(
        data={
            "meta": {"message": MESSAGE_EVENT},
            "data": [EVENT_CLIENT_2_CONNECTED],
        }
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    switch_2 = hass.states.get("switch.poe_client_2")
    assert switch_2 is not None

    aioclient_mock.put(
        f"https://{controller.host}:1234/api/s/{controller.site}/rest/device/mock-id",
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_off", {"entity_id": "switch.poe_client_1"}, blocking=True
    )
    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 2
    assert aioclient_mock.call_count == 11
    assert aioclient_mock.mock_calls[10][2] == {
        "port_overrides": [{"port_idx": 1, "portconf_id": "1a1", "poe_mode": "off"}]
    }

    await hass.services.async_call(
        SWITCH_DOMAIN, "turn_on", {"entity_id": "switch.poe_client_1"}, blocking=True
    )
    assert aioclient_mock.call_count == 12
    assert aioclient_mock.mock_calls[11][2] == {
        "port_overrides": [{"port_idx": 1, "portconf_id": "1a1", "poe_mode": "auto"}]
    }


async def test_ignore_multiple_poe_clients_on_same_port(hass, aioclient_mock):
    """Ignore when there are multiple POE driven clients on same port.

    If there is a non-UniFi switch powered by POE,
    clients will be transparently marked as having POE as well.
    """
    await setup_unifi_integration(
        hass,
        aioclient_mock,
        clients_response=POE_SWITCH_CLIENTS,
        devices_response=[DEVICE_1],
    )

    assert len(hass.states.async_entity_ids(TRACKER_DOMAIN)) == 3

    switch_1 = hass.states.get("switch.poe_client_1")
    switch_2 = hass.states.get("switch.poe_client_2")
    assert switch_1 is None
    assert switch_2 is None


async def test_restore_client_succeed(hass, aioclient_mock):
    """Test that RestoreEntity works as expected."""
    POE_DEVICE = {
        "device_id": "12345",
        "ip": "1.0.1.1",
        "mac": "00:00:00:00:01:01",
        "last_seen": 1562600145,
        "model": "US16P150",
        "name": "POE Switch",
        "port_overrides": [
            {
                "poe_mode": "off",
                "port_idx": 1,
                "portconf_id": "5f3edd2aba4cc806a19f2db2",
            }
        ],
        "port_table": [
            {
                "media": "GE",
                "name": "Port 1",
                "op_mode": "switch",
                "poe_caps": 7,
                "poe_class": "Unknown",
                "poe_current": "0.00",
                "poe_enable": False,
                "poe_good": False,
                "poe_mode": "off",
                "poe_power": "0.00",
                "poe_voltage": "0.00",
                "port_idx": 1,
                "port_poe": True,
                "portconf_id": "5f3edd2aba4cc806a19f2db2",
                "up": False,
            },
        ],
        "state": 1,
        "type": "usw",
        "version": "4.0.42.10433",
    }
    POE_CLIENT = {
        "hostname": "poe_client",
        "ip": "1.0.0.1",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
        "name": "POE Client",
        "oui": "Producer",
    }

    fake_state = core.State(
        "switch.poe_client",
        "off",
        {
            "power": "0.00",
            "switch": POE_DEVICE["mac"],
            "port": 1,
            "poe_mode": "auto",
        },
    )

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
        SWITCH_DOMAIN,
        UNIFI_DOMAIN,
        f'{POE_SWITCH}-{POE_CLIENT["mac"]}',
        suggested_object_id=POE_CLIENT["hostname"],
        config_entry=config_entry,
    )

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=fake_state,
    ):
        await setup_unifi_integration(
            hass,
            aioclient_mock,
            options={
                CONF_TRACK_CLIENTS: False,
                CONF_TRACK_DEVICES: False,
            },
            clients_response=[],
            devices_response=[POE_DEVICE],
            clients_all_response=[POE_CLIENT],
        )

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    poe_client = hass.states.get("switch.poe_client")
    assert poe_client.state == "off"


async def test_restore_client_no_old_state(hass, aioclient_mock):
    """Test that RestoreEntity without old state makes entity unavailable."""
    POE_DEVICE = {
        "device_id": "12345",
        "ip": "1.0.1.1",
        "mac": "00:00:00:00:01:01",
        "last_seen": 1562600145,
        "model": "US16P150",
        "name": "POE Switch",
        "port_overrides": [
            {
                "poe_mode": "off",
                "port_idx": 1,
                "portconf_id": "5f3edd2aba4cc806a19f2db2",
            }
        ],
        "port_table": [
            {
                "media": "GE",
                "name": "Port 1",
                "op_mode": "switch",
                "poe_caps": 7,
                "poe_class": "Unknown",
                "poe_current": "0.00",
                "poe_enable": False,
                "poe_good": False,
                "poe_mode": "off",
                "poe_power": "0.00",
                "poe_voltage": "0.00",
                "port_idx": 1,
                "port_poe": True,
                "portconf_id": "5f3edd2aba4cc806a19f2db2",
                "up": False,
            },
        ],
        "state": 1,
        "type": "usw",
        "version": "4.0.42.10433",
    }
    POE_CLIENT = {
        "hostname": "poe_client",
        "ip": "1.0.0.1",
        "is_wired": True,
        "last_seen": 1562600145,
        "mac": "00:00:00:00:00:01",
        "name": "POE Client",
        "oui": "Producer",
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
        SWITCH_DOMAIN,
        UNIFI_DOMAIN,
        f'{POE_SWITCH}-{POE_CLIENT["mac"]}',
        suggested_object_id=POE_CLIENT["hostname"],
        config_entry=config_entry,
    )

    await setup_unifi_integration(
        hass,
        aioclient_mock,
        options={
            CONF_TRACK_CLIENTS: False,
            CONF_TRACK_DEVICES: False,
        },
        clients_response=[],
        devices_response=[POE_DEVICE],
        clients_all_response=[POE_CLIENT],
    )

    assert len(hass.states.async_entity_ids(SWITCH_DOMAIN)) == 1

    poe_client = hass.states.get("switch.poe_client")
    assert poe_client.state == "unavailable"  # self.poe_mode is None
