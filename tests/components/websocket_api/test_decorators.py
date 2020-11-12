"""Test decorators."""
from homeassistant.components import http, websocket_api


async def test_async_response_request_context(hass, websocket_client):
    """Test we can access current request."""

    @websocket_api.websocket_command({"type": "test-get-request-async"})
    @websocket_api.async_response
    async def async_get_request(hass, connection, msg):
        connection.send_result(msg["id"], http.current_request.get().path)

    @websocket_api.websocket_command({"type": "test-get-request"})
    def get_request(hass, connection, msg):
        connection.send_result(msg["id"], http.current_request.get().path)

    websocket_api.async_register_command(hass, async_get_request)
    websocket_api.async_register_command(hass, get_request)

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "test-get-request",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == "/api/websocket"

    await websocket_client.send_json(
        {
            "id": 6,
            "type": "test-get-request-async",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 6
    assert msg["success"]
    assert msg["result"] == "/api/websocket"
