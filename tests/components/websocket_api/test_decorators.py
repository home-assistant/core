"""Test decorators."""

import voluptuous as vol

from homeassistant.components import http, websocket_api
from homeassistant.core import HomeAssistant


async def test_async_response_request_context(
    hass: HomeAssistant, websocket_client
) -> None:
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

    @websocket_api.websocket_command(
        {"type": "test-get-request-with-arg", vol.Required("arg"): str}
    )
    def get_with_arg_request(hass, connection, msg):
        handle_request(http.current_request.get(), connection, msg)

    websocket_api.async_register_command(hass, executor_get_request)
    websocket_api.async_register_command(hass, async_get_request)
    websocket_api.async_register_command(hass, get_request)
    websocket_api.async_register_command(hass, get_with_arg_request)

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

    await websocket_client.send_json(
        {
            "id": 8,
            "type": "test-get-request-with-arg",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 8
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
    assert (
        msg["error"]["message"] == "required key not provided @ data['arg']. Got None"
    )

    await websocket_client.send_json(
        {
            "id": 9,
            "type": "test-get-request-with-arg",
            "arg": "dog",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 9
    assert msg["success"]
    assert msg["result"] == "/api/websocket"

    await websocket_client.send_json(
        {
            "id": -1,
            "type": "test-get-request-with-arg",
            "arg": "dog",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == -1
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
    assert msg["error"]["message"] == "Message incorrectly formatted."

    await websocket_client.send_json(
        {
            "id": 10,
            "type": "test-get-request",
            "not_valid": "dog",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 10
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_format"
    assert msg["error"]["message"] == (
        "extra keys not allowed. "
        "Got {'id': 10, 'type': 'test-get-request', 'not_valid': 'dog'}"
    )


async def test_supervisor_only(hass: HomeAssistant, websocket_client) -> None:
    """Test that only the Supervisor can make requests."""

    @websocket_api.ws_require_user(only_supervisor=True)
    @websocket_api.websocket_command({"type": "test-require-supervisor-user"})
    def require_supervisor_request(hass, connection, msg):
        connection.send_result(msg["id"])

    websocket_api.async_register_command(hass, require_supervisor_request)

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "test-require-supervisor-user",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "only_supervisor"
