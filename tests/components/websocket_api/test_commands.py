"""Tests for WebSocket API commands."""
from async_timeout import timeout

from homeassistant.components.websocket_api import const
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
)
from homeassistant.components.websocket_api.const import URL
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


async def test_call_service(hass, websocket_client):
    """Test call service command."""
    calls = []

    @callback
    def service_call(call):
        calls.append(call)

    hass.services.async_register("domain_test", "test_service", service_call)

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "call_service",
            "domain": "domain_test",
            "service": "test_service",
            "service_data": {"hello": "world"},
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    assert len(calls) == 1
    call = calls[0]

    assert call.domain == "domain_test"
    assert call.service == "test_service"
    assert call.data == {"hello": "world"}


async def test_call_service_not_found(hass, websocket_client):
    """Test call service command."""
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "call_service",
            "domain": "domain_test",
            "service": "test_service",
            "service_data": {"hello": "world"},
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_NOT_FOUND


async def test_call_service_child_not_found(hass, websocket_client):
    """Test not reporting not found errors if it's not the called service."""

    async def serv_handler(call):
        await hass.services.async_call("non", "existing")

    hass.services.async_register("domain_test", "test_service", serv_handler)

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "call_service",
            "domain": "domain_test",
            "service": "test_service",
            "service_data": {"hello": "world"},
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_HOME_ASSISTANT_ERROR


async def test_call_service_error(hass, websocket_client):
    """Test call service command with error."""

    @callback
    def ha_error_call(_):
        raise HomeAssistantError("error_message")

    hass.services.async_register("domain_test", "ha_error", ha_error_call)

    async def unknown_error_call(_):
        raise ValueError("value_error")

    hass.services.async_register("domain_test", "unknown_error", unknown_error_call)

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "call_service",
            "domain": "domain_test",
            "service": "ha_error",
        }
    )

    msg = await websocket_client.receive_json()
    print(msg)
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"] is False
    assert msg["error"]["code"] == "home_assistant_error"
    assert msg["error"]["message"] == "error_message"

    await websocket_client.send_json(
        {
            "id": 6,
            "type": "call_service",
            "domain": "domain_test",
            "service": "unknown_error",
        }
    )

    msg = await websocket_client.receive_json()
    print(msg)
    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"] is False
    assert msg["error"]["code"] == "unknown_error"
    assert msg["error"]["message"] == "value_error"


async def test_subscribe_unsubscribe_events(hass, websocket_client):
    """Test subscribe/unsubscribe events command."""
    init_count = sum(hass.bus.async_listeners().values())

    await websocket_client.send_json(
        {"id": 5, "type": "subscribe_events", "event_type": "test_event"}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    # Verify we have a new listener
    assert sum(hass.bus.async_listeners().values()) == init_count + 1

    hass.bus.async_fire("ignore_event")
    hass.bus.async_fire("test_event", {"hello": "world"})
    hass.bus.async_fire("ignore_event")

    with timeout(3):
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == "event"
    event = msg["event"]

    assert event["event_type"] == "test_event"
    assert event["data"] == {"hello": "world"}
    assert event["origin"] == "LOCAL"

    await websocket_client.send_json(
        {"id": 6, "type": "unsubscribe_events", "subscription": 5}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    # Check our listener got unsubscribed
    assert sum(hass.bus.async_listeners().values()) == init_count


async def test_get_states(hass, websocket_client):
    """Test get_states command."""
    hass.states.async_set("greeting.hello", "world")
    hass.states.async_set("greeting.bye", "universe")

    await websocket_client.send_json({"id": 5, "type": "get_states"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    states = []
    for state in hass.states.async_all():
        state = state.as_dict()
        state["last_changed"] = state["last_changed"].isoformat()
        state["last_updated"] = state["last_updated"].isoformat()
        states.append(state)

    assert msg["result"] == states


async def test_get_services(hass, websocket_client):
    """Test get_services command."""
    await websocket_client.send_json({"id": 5, "type": "get_services"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == hass.services.async_services()


async def test_get_config(hass, websocket_client):
    """Test get_config command."""
    await websocket_client.send_json({"id": 5, "type": "get_config"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    if "components" in msg["result"]:
        msg["result"]["components"] = set(msg["result"]["components"])
    if "whitelist_external_dirs" in msg["result"]:
        msg["result"]["whitelist_external_dirs"] = set(
            msg["result"]["whitelist_external_dirs"]
        )

    assert msg["result"] == hass.config.as_dict()


async def test_ping(websocket_client):
    """Test get_panels command."""
    await websocket_client.send_json({"id": 5, "type": "ping"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "pong"


async def test_call_service_context_with_user(hass, aiohttp_client, hass_access_token):
    """Test that the user is set in the service call context."""
    assert await async_setup_component(hass, "websocket_api", {})

    calls = async_mock_service(hass, "domain_test", "test_service")
    client = await aiohttp_client(hass.http.app)

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws.send_json({"type": TYPE_AUTH, "access_token": hass_access_token})

        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_OK

        await ws.send_json(
            {
                "id": 5,
                "type": "call_service",
                "domain": "domain_test",
                "service": "test_service",
                "service_data": {"hello": "world"},
            }
        )

        msg = await ws.receive_json()
        assert msg["success"]

        refresh_token = await hass.auth.async_validate_access_token(hass_access_token)

        assert len(calls) == 1
        call = calls[0]
        assert call.domain == "domain_test"
        assert call.service == "test_service"
        assert call.data == {"hello": "world"}
        assert call.context.user_id == refresh_token.user.id


async def test_subscribe_requires_admin(websocket_client, hass_admin_user):
    """Test subscribing events without being admin."""
    hass_admin_user.groups = []
    await websocket_client.send_json(
        {"id": 5, "type": "subscribe_events", "event_type": "test_event"}
    )

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_UNAUTHORIZED


async def test_states_filters_visible(hass, hass_admin_user, websocket_client):
    """Test we only get entities that we're allowed to see."""
    hass_admin_user.mock_policy({"entities": {"entity_ids": {"test.entity": True}}})
    hass.states.async_set("test.entity", "hello")
    hass.states.async_set("test.not_visible_entity", "invisible")
    await websocket_client.send_json({"id": 5, "type": "get_states"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    assert len(msg["result"]) == 1
    assert msg["result"][0]["entity_id"] == "test.entity"


async def test_get_states_not_allows_nan(hass, websocket_client):
    """Test get_states command not allows NaN floats."""
    hass.states.async_set("greeting.hello", "world", {"hello": float("NaN")})

    await websocket_client.send_json({"id": 5, "type": "get_states"})

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == const.ERR_UNKNOWN_ERROR


async def test_subscribe_unsubscribe_events_whitelist(
    hass, websocket_client, hass_admin_user
):
    """Test subscribe/unsubscribe events on whitelist."""
    hass_admin_user.groups = []

    await websocket_client.send_json(
        {"id": 5, "type": "subscribe_events", "event_type": "not-in-whitelist"}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"

    await websocket_client.send_json(
        {"id": 6, "type": "subscribe_events", "event_type": "themes_updated"}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    hass.bus.async_fire("themes_updated")

    with timeout(3):
        msg = await websocket_client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == "event"
    event = msg["event"]
    assert event["event_type"] == "themes_updated"
    assert event["origin"] == "LOCAL"


async def test_subscribe_unsubscribe_events_state_changed(
    hass, websocket_client, hass_admin_user
):
    """Test subscribe/unsubscribe state_changed events."""
    hass_admin_user.groups = []
    hass_admin_user.mock_policy({"entities": {"entity_ids": {"light.permitted": True}}})

    await websocket_client.send_json(
        {"id": 7, "type": "subscribe_events", "event_type": "state_changed"}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    hass.states.async_set("light.not_permitted", "on")
    hass.states.async_set("light.permitted", "on")

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == "event"
    assert msg["event"]["event_type"] == "state_changed"
    assert msg["event"]["data"]["entity_id"] == "light.permitted"


async def test_render_template_renders_template(
    hass, websocket_client, hass_admin_user
):
    """Test simple template is rendered and updated."""
    hass.states.async_set("light.test", "on")

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "render_template",
            "template": "State is: {{ states('light.test') }}",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "event"
    event = msg["event"]
    assert event == {"result": "State is: on"}

    hass.states.async_set("light.test", "off")
    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "event"
    event = msg["event"]
    assert event == {"result": "State is: off"}


async def test_render_template_with_manual_entity_ids(
    hass, websocket_client, hass_admin_user
):
    """Test that updates to specified entity ids cause a template rerender."""
    hass.states.async_set("light.test", "on")
    hass.states.async_set("light.test2", "on")

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "render_template",
            "template": "State is: {{ states('light.test') }}",
            "entity_ids": ["light.test2"],
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "event"
    event = msg["event"]
    assert event == {"result": "State is: on"}

    hass.states.async_set("light.test2", "off")
    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "event"
    event = msg["event"]
    assert event == {"result": "State is: on"}


async def test_render_template_returns_with_match_all(
    hass, websocket_client, hass_admin_user
):
    """Test that a template that would match with all entities still return success."""
    await websocket_client.send_json(
        {"id": 5, "type": "render_template", "template": "State is: {{ 42 }}"}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]


async def test_manifest_list(hass, websocket_client):
    """Test loading manifests."""
    http = await async_get_integration(hass, "http")
    websocket_api = await async_get_integration(hass, "websocket_api")

    await websocket_client.send_json({"id": 5, "type": "manifest/list"})

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert sorted(msg["result"], key=lambda manifest: manifest["domain"]) == [
        http.manifest,
        websocket_api.manifest,
    ]


async def test_manifest_get(hass, websocket_client):
    """Test getting a manifest."""
    hue = await async_get_integration(hass, "hue")

    await websocket_client.send_json(
        {"id": 6, "type": "manifest/get", "integration": "hue"}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 6
    assert msg["type"] == const.TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == hue.manifest

    # Non existing
    await websocket_client.send_json(
        {"id": 7, "type": "manifest/get", "integration": "non_existing"}
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 7
    assert msg["type"] == const.TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"
