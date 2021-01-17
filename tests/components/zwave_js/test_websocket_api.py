"""Test the Z-Wave JS Websocket API."""
from unittest.mock import patch

from zwave_js_server.event import Event

from homeassistant.components.zwave_js.websocket_api import ENTRY_ID, ID, TYPE


async def test_websocket_api(hass, integration, hass_ws_client):
    """Test the network_status websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    await ws_client.send_json(
        {ID: 2, TYPE: "zwave_js/network_status", ENTRY_ID: entry.entry_id}
    )
    msg = await ws_client.receive_json()
    result = msg["result"]

    assert result["client"]["ws_server_url"] == "ws://test:3000/zjs"
    assert result["client"]["server_version"] == "1.0.0"


async def test_add_node(
    hass, integration, client, hass_ws_client, nortek_thermostat_added_event
):
    """Test the add_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    with patch(
        "zwave_js_server.model.controller.Controller.async_begin_inclusion",
        return_value=True,
    ):
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
    with patch(
        "zwave_js_server.model.controller.Controller.async_stop_inclusion",
        return_value=True,
    ):
        await ws_client.send_json(
            {ID: 4, TYPE: "zwave_js/stop_inclusion", ENTRY_ID: entry.entry_id}
        )

        msg = await ws_client.receive_json()
        assert msg["success"]

    with patch(
        "zwave_js_server.model.controller.Controller.async_stop_exclusion",
        return_value=True,
    ):
        await ws_client.send_json(
            {ID: 5, TYPE: "zwave_js/stop_exclusion", ENTRY_ID: entry.entry_id}
        )

        msg = await ws_client.receive_json()
        assert msg["success"]


async def test_remove_node(hass, integration, client, hass_ws_client):
    """Test the add_node websocket command."""
    entry = integration
    ws_client = await hass_ws_client(hass)

    with patch(
        "zwave_js_server.model.controller.Controller.async_begin_exclusion",
        return_value=True,
    ):
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
