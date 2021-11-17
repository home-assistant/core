"""Test decorators."""
from homeassistant.components import http, websocket_api
import homeassistant.helpers.config_validation as cv


async def test_async_response_request_context(hass, websocket_client):
    """Test we can access current request."""

    def handle_request(request, connection, msg):
        if request is not None:
            connection.send_result(msg["id"], request.path)
        else:
            connection.send_error(msg["id"], "not_found", "")

    @websocket_api.websocket_command({"type": "test-get-request-executor"})
    @websocket_api.async_response
    async def executor_get_request(hass, connection, msg):
        handle_request(
            await hass.async_add_executor_job(http.current_request.get), connection, msg
        )

    @websocket_api.websocket_command({"type": "test-get-request-async"})
    @websocket_api.async_response
    async def async_get_request(hass, connection, msg):
        handle_request(http.current_request.get(), connection, msg)

    @websocket_api.websocket_command({"type": "test-get-request"})
    def get_request(hass, connection, msg):
        handle_request(http.current_request.get(), connection, msg)

    websocket_api.async_register_command(hass, executor_get_request)
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

    await websocket_client.send_json(
        {
            "id": 7,
            "type": "test-get-request-executor",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


async def test_additional_validators(hass, websocket_client):
    """Test that additional validators can be applied."""

    @websocket_api.websocket_command({"type": "test"}, cv.has_at_least_one_key("test"))
    @websocket_api.async_response
    async def async_test_command(hass, connection, msg):
        connection.send_result(msg["id"], "ok")

    websocket_api.async_register_command(hass, async_test_command)

    await websocket_client.send_json(
        {
            "id": 1,
            "type": "test",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 1
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
