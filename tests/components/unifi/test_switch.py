"""UniFi POE control platform tests."""
from copy import deepcopy

from homeassistant import config_entries
from homeassistant.components import unifi
import homeassistant.components.switch as switch
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component

from .test_controller import (
    CONTROLLER_HOST,
    ENTRY_CONFIG,
    SITES,
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
    "mac": "00:00:00:00:01:02",
    "name": "Block Client 2",
    "noted": True,
    "oui": "Producer",
}


async def test_platform_manually_configured(hass):
    """Test that we do not discover anything or try to set up a controller."""
    assert (
        await async_setup_component(
            hass, switch.DOMAIN, {switch.DOMAIN: {"platform": "unifi"}}
        )
        is True
    )
    assert unifi.DOMAIN not in hass.data


async def test_no_clients(hass):
    """Test the update_clients function when no clients are found."""
    controller = await setup_unifi_integration(
        hass,
        options={
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 1


async def test_controller_not_client(hass):
    """Test that the controller doesn't become a switch."""
    controller = await setup_unifi_integration(
        hass,
        options={
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
        clients_response=[CONTROLLER_HOST],
        devices_response=[DEVICE_1],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 1
    cloudkey = hass.states.get("switch.cloud_key")
    assert cloudkey is None


async def test_not_admin(hass):
    """Test that switch platform only work on an admin account."""
    sites = deepcopy(SITES)
    sites["Site name"]["role"] = "not admin"
    controller = await setup_unifi_integration(
        hass,
        options={
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
        sites=sites,
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 1


async def test_switches(hass):
    """Test the update_items function with some clients."""
    controller = await setup_unifi_integration(
        hass,
        options={
            unifi.CONF_BLOCK_CLIENT: [BLOCKED["mac"], UNBLOCKED["mac"]],
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
        clients_response=[CLIENT_1, CLIENT_4],
        devices_response=[DEVICE_1],
        clients_all_response=[BLOCKED, UNBLOCKED, CLIENT_1],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 4

    switch_1 = hass.states.get("switch.poe_client_1")
    assert switch_1 is not None
    assert switch_1.state == "on"
    assert switch_1.attributes["power"] == "2.56"
    assert switch_1.attributes["switch"] == "00:00:00:00:01:01"
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


async def test_new_client_discovered_on_block_control(hass):
    """Test if 2nd update has a new client."""
    controller = await setup_unifi_integration(
        hass,
        options={
            unifi.CONF_BLOCK_CLIENT: [BLOCKED["mac"]],
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
        clients_all_response=[BLOCKED],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 2

    controller.api.websocket._data = {
        "meta": {"message": "sta:sync"},
        "data": [BLOCKED],
    }
    controller.api.session_handler("data")

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert len(controller.mock_requests) == 4
    assert len(hass.states.async_all()) == 2
    assert controller.mock_requests[3] == {
        "json": {"mac": "00:00:00:00:01:01", "cmd": "block-sta"},
        "method": "post",
        "path": "s/{site}/cmd/stamgr/",
    }

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.block_client_1"}, blocking=True
    )
    assert len(controller.mock_requests) == 5
    assert controller.mock_requests[4] == {
        "json": {"mac": "00:00:00:00:01:01", "cmd": "unblock-sta"},
        "method": "post",
        "path": "s/{site}/cmd/stamgr/",
    }


async def test_new_client_discovered_on_poe_control(hass):
    """Test if 2nd update has a new client."""
    controller = await setup_unifi_integration(
        hass,
        options={
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
        clients_response=[CLIENT_1],
        devices_response=[DEVICE_1],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 2

    controller.api.websocket._data = {
        "meta": {"message": "sta:sync"},
        "data": [CLIENT_2],
    }
    controller.api.session_handler("data")

    # Calling a service will trigger the updates to run
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.poe_client_1"}, blocking=True
    )
    assert len(controller.mock_requests) == 4
    assert len(hass.states.async_all()) == 3
    assert controller.mock_requests[3] == {
        "json": {
            "port_overrides": [{"port_idx": 1, "portconf_id": "1a1", "poe_mode": "off"}]
        },
        "method": "put",
        "path": "s/{site}/rest/device/mock-id",
    }

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.poe_client_1"}, blocking=True
    )
    assert len(controller.mock_requests) == 5
    assert controller.mock_requests[3] == {
        "json": {
            "port_overrides": [
                {"port_idx": 1, "portconf_id": "1a1", "poe_mode": "auto"}
            ]
        },
        "method": "put",
        "path": "s/{site}/rest/device/mock-id",
    }

    switch_2 = hass.states.get("switch.poe_client_2")
    assert switch_2 is not None
    assert switch_2.state == "on"


async def test_ignore_multiple_poe_clients_on_same_port(hass):
    """Ignore when there are multiple POE driven clients on same port.

    If there is a non-UniFi switch powered by POE,
    clients will be transparently marked as having POE as well.
    """
    controller = await setup_unifi_integration(
        hass, clients_response=POE_SWITCH_CLIENTS, devices_response=[DEVICE_1],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 4

    switch_1 = hass.states.get("switch.poe_client_1")
    switch_2 = hass.states.get("switch.poe_client_2")
    assert switch_1 is None
    assert switch_2 is None


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
        switch.DOMAIN,
        unifi.DOMAIN,
        "poe-{}".format(CLIENT_1["mac"]),
        suggested_object_id=CLIENT_1["hostname"],
        config_entry=config_entry,
    )
    registry.async_get_or_create(
        switch.DOMAIN,
        unifi.DOMAIN,
        "poe-{}".format(CLIENT_2["mac"]),
        suggested_object_id=CLIENT_2["hostname"],
        config_entry=config_entry,
    )

    controller = await setup_unifi_integration(
        hass,
        options={
            unifi.CONF_BLOCK_CLIENT: ["random mac"],
            unifi.const.CONF_TRACK_CLIENTS: False,
            unifi.const.CONF_TRACK_DEVICES: False,
        },
        clients_response=[CLIENT_2],
        devices_response=[DEVICE_1],
        clients_all_response=[CLIENT_1],
    )

    assert len(controller.mock_requests) == 3
    assert len(hass.states.async_all()) == 3

    device_1 = hass.states.get("switch.client_1")
    assert device_1 is not None
