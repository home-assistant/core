"""Test the Z-Wave JS Websocket API."""

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
