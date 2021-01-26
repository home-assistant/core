"""Test the Z-Wave JS Websocket API."""
from unittest.mock import patch

from zwave_js_server.event import Event

from homeassistant.components.zwave_js.api import ENTRY_ID, ID, NODE_ID, TYPE
from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.helpers.device_registry import async_get_registry


async def test_websocket_api(hass, integration, multisensor_6, hass_ws_client):
    """Test the network and node status websocket commands."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {ID: 2, TYPE: "zwave_js/network_status", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result["client"]["ws_server_url"] == "ws://test:3000/zjs"
    assert result["client"]["server_version"] == "1.0.0"

    node = multisensor_6
    await ws_client.send_json(
        {
            ID: 3,
            TYPE: "zwave_js/node_status",
            ENTRY_ID: entry.entry_id,
            NODE_ID: node.node_id,
        }
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result[NODE_ID] == 52
    assert result["ready"]
    assert result["is_routing"]
    assert not result["is_secure"]
    assert result["status"] == 1


async def test_add_node(
    hass, integration, client, hass_ws_client, nortek_thermostat_added_event
):
    """Test the add_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 3, TYPE: "zwave_js/add_node", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    event = Event(
        type="inclusion started",
        data={
            "source": "controller",
            "event": "inclusion started",
            "secure": False,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "inclusion started"

    client.driver.receive_event(nortek_thermostat_added_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node added"


async def test_cancel_inclusion_exclusion(hass, integration, client, hass_ws_client):
    """Test cancelling the inclusion and exclusion process."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 4, TYPE: "zwave_js/stop_inclusion", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    await ws_client.send_json(
        {ID: 5, TYPE: "zwave_js/stop_exclusion", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]


async def test_remove_node(
    hass,
    integration,
    client,
    hass_ws_client,
    nortek_thermostat,
    nortek_thermostat_removed_event,
):
    """Test the remove_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    client.async_send_command.return_value = {"success": True}

    await ws_client.send_json(
        {ID: 3, TYPE: "zwave_js/remove_node", ENTRY_ID: entry.entry_id}
    )

    msg = await ws_client.receive_json()
    assert msg["success"]

    event = Event(
        type="exclusion started",
        data={
            "source": "controller",
            "event": "exclusion started",
            "secure": False,
        },
    )
    client.driver.receive_event(event)

    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "exclusion started"

    # Add mock node to controller
    client.driver.controller.nodes[67] = nortek_thermostat

    dev_reg = await async_get_registry(hass)

    # Create device registry entry for mock node
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "3245146787-67")},
        name="Node 67",
    )

    # Fire node removed event
    client.driver.receive_event(nortek_thermostat_removed_event)
    msg = await ws_client.receive_json()
    assert msg["event"]["event"] == "node removed"

    # Verify device was removed from device registry
    device = dev_reg.async_get_device(
        identifiers={(DOMAIN, "3245146787-67")},
    )
    assert device is None


async def test_dump_view(integration, hass_client):
    """Test the HTTP dump view."""
    client = await hass_client()
    with patch(
        "zwave_js_server.dump.dump_msgs",
        return_value=[{"hello": "world"}, {"second": "msg"}],
    ):
        resp = await client.get(f"/api/zwave_js/dump/{integration.entry_id}")
    assert resp.status == 200
    assert await resp.text() == '{"hello": "world"}\n{"second": "msg"}\n'


async def test_dump_view_invalid_entry_id(integration, hass_client):
    """Test an invalid config entry id parameter."""
    client = await hass_client()
    resp = await client.get("/api/zwave_js/dump/INVALID")
    assert resp.status == 400
