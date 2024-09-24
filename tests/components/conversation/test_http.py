"""The tests for the HTTP API of the Conversation component."""

from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.conversation import default_agent
from homeassistant.components.conversation.const import DATA_DEFAULT_ENTITY
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, entity_registry as er, intent
from homeassistant.setup import async_setup_component

from . import MockAgent

from tests.common import async_mock_service
from tests.typing import ClientSessionGenerator, WebSocketGenerator

AGENT_ID_OPTIONS = [
    None,
    # Old value of conversation.HOME_ASSISTANT_AGENT,
    "homeassistant",
    # Current value of conversation.HOME_ASSISTANT_AGENT,
    "conversation.home_assistant",
]


class OrderBeerIntentHandler(intent.IntentHandler):
    """Handle OrderBeer intent."""

    intent_type = "OrderBeer"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Return speech response."""
        beer_style = intent_obj.slots["beer_style"]["value"]
        response = intent_obj.create_response()
        response.async_set_speech(f"You ordered a {beer_style}")
        return response


@pytest.mark.parametrize("agent_id", AGENT_ID_OPTIONS)
async def test_http_processing_intent(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    agent_id,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test processing intent via HTTP API."""
    # Add an alias
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity("light.kitchen", aliases={"my cool light"})
    hass.states.async_set("light.kitchen", "off")

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    client = await hass_client()
    data: dict[str, Any] = {"text": "turn on my cool light"}
    if agent_id:
        data["agent_id"] = agent_id
    resp = await client.post("/api/conversation/process", json=data)

    assert resp.status == HTTPStatus.OK
    assert len(calls) == 1
    data = await resp.json()

    assert data == snapshot


async def test_http_api_no_match(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the HTTP conversation API with an intent match failure."""
    client = await hass_client()

    # Shouldn't match any intents
    resp = await client.post("/api/conversation/process", json={"text": "do something"})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == snapshot
    assert data["response"]["response_type"] == "error"
    assert data["response"]["data"]["code"] == "no_intent_match"


async def test_http_api_handle_failure(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the HTTP conversation API with an error during handling."""
    client = await hass_client()

    hass.states.async_set("light.kitchen", "off")

    # Raise an error during intent handling
    def async_handle_error(*args, **kwargs):
        raise intent.IntentHandleError

    with patch("homeassistant.helpers.intent.async_handle", new=async_handle_error):
        resp = await client.post(
            "/api/conversation/process", json={"text": "turn on the kitchen"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == snapshot
    assert data["response"]["response_type"] == "error"
    assert data["response"]["data"]["code"] == "failed_to_handle"


async def test_http_api_unexpected_failure(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the HTTP conversation API with an unexpected error during handling."""
    client = await hass_client()

    hass.states.async_set("light.kitchen", "off")

    # Raise an "unexpected" error during intent handling
    def async_handle_error(*args, **kwargs):
        raise intent.IntentUnexpectedError

    with patch("homeassistant.helpers.intent.async_handle", new=async_handle_error):
        resp = await client.post(
            "/api/conversation/process", json={"text": "turn on the kitchen"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == snapshot
    assert data["response"]["response_type"] == "error"
    assert data["response"]["data"]["code"] == "unknown"


async def test_http_api_wrong_data(
    hass: HomeAssistant, init_components, hass_client: ClientSessionGenerator
) -> None:
    """Test the HTTP conversation API."""
    client = await hass_client()

    resp = await client.post("/api/conversation/process", json={"text": 123})
    assert resp.status == HTTPStatus.BAD_REQUEST

    resp = await client.post("/api/conversation/process", json={})
    assert resp.status == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize(
    "payload",
    [
        {
            "text": "Test Text",
        },
        {
            "text": "Test Text",
            "language": "test-language",
        },
        {
            "text": "Test Text",
            "conversation_id": "test-conv-id",
        },
        {
            "text": "Test Text",
            "conversation_id": None,
        },
        {
            "text": "Test Text",
            "conversation_id": "test-conv-id",
            "language": "test-language",
        },
        {
            "text": "Test Text",
            "agent_id": "homeassistant",
        },
    ],
)
async def test_ws_api(
    hass: HomeAssistant,
    init_components,
    hass_ws_client: WebSocketGenerator,
    payload,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Websocket conversation API."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "conversation/process", **payload})

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot
    assert msg["result"]["response"]["data"]["code"] == "no_intent_match"


@pytest.mark.parametrize("agent_id", AGENT_ID_OPTIONS)
async def test_ws_prepare(
    hass: HomeAssistant, init_components, hass_ws_client: WebSocketGenerator, agent_id
) -> None:
    """Test the Websocket prepare conversation API."""
    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)

    # No intents should be loaded yet
    assert not agent._lang_intents.get(hass.config.language)

    client = await hass_ws_client(hass)

    msg = {"type": "conversation/prepare"}
    if agent_id is not None:
        msg["agent_id"] = agent_id
    await client.send_json_auto_id(msg)

    msg = await client.receive_json()

    assert msg["success"]

    # Intents should now be load
    assert agent._lang_intents.get(hass.config.language)


async def test_get_agent_list(
    hass: HomeAssistant,
    init_components,
    mock_conversation_agent: MockAgent,
    mock_agent_support_all: MockAgent,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test getting agent info."""
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "conversation/agent/list"})
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == snapshot

    await client.send_json_auto_id(
        {"type": "conversation/agent/list", "language": "smurfish"}
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == snapshot

    await client.send_json_auto_id(
        {"type": "conversation/agent/list", "language": "en"}
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == snapshot

    await client.send_json_auto_id(
        {"type": "conversation/agent/list", "language": "en-UK"}
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == snapshot

    await client.send_json_auto_id(
        {"type": "conversation/agent/list", "language": "de"}
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == snapshot

    await client.send_json_auto_id(
        {"type": "conversation/agent/list", "language": "de", "country": "ch"}
    )
    msg = await client.receive_json()
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == snapshot


async def test_ws_hass_agent_debug(
    hass: HomeAssistant,
    init_components,
    hass_ws_client: WebSocketGenerator,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test homeassistant agent debug websocket command."""
    client = await hass_ws_client(hass)

    kitchen_area = area_registry.async_create("kitchen")
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity(
        "light.kitchen",
        aliases={"my cool light"},
        area_id=kitchen_area.id,
    )
    await hass.async_block_till_done()
    hass.states.async_set("light.kitchen", "off")

    on_calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    off_calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")

    await client.send_json_auto_id(
        {
            "type": "conversation/agent/homeassistant/debug",
            "sentences": [
                "turn on my cool light",
                "turn my cool light off",
                "turn on all lights in the kitchen",
                "how many lights are on in the kitchen?",
                "this will not match anything",  # None in results
            ],
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot

    # Last sentence should be a failed match
    assert msg["result"]["results"][-1] is None

    # Light state should not have been changed
    assert len(on_calls) == 0
    assert len(off_calls) == 0


async def test_ws_hass_agent_debug_null_result(
    hass: HomeAssistant,
    init_components,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test homeassistant agent debug websocket command with a null result."""
    client = await hass_ws_client(hass)

    async def async_recognize(self, user_input, *args, **kwargs):
        if user_input.text == "bad sentence":
            return None

        return await self.async_recognize(user_input, *args, **kwargs)

    with patch(
        "homeassistant.components.conversation.default_agent.DefaultAgent.async_recognize",
        async_recognize,
    ):
        await client.send_json_auto_id(
            {
                "type": "conversation/agent/homeassistant/debug",
                "sentences": [
                    "bad sentence",
                ],
            }
        )

        msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot
    assert msg["result"]["results"] == [None]


async def test_ws_hass_agent_debug_out_of_range(
    hass: HomeAssistant,
    init_components,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test homeassistant agent debug websocket command with an out of range entity."""
    test_light = entity_registry.async_get_or_create("light", "demo", "1234")
    hass.states.async_set(
        test_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "test light"}
    )

    client = await hass_ws_client(hass)

    # Brightness is in range (0-100)
    await client.send_json_auto_id(
        {
            "type": "conversation/agent/homeassistant/debug",
            "sentences": [
                "set test light brightness to 100%",
            ],
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot

    results = msg["result"]["results"]
    assert len(results) == 1
    assert results[0]["match"]

    # Brightness is out of range
    await client.send_json_auto_id(
        {
            "type": "conversation/agent/homeassistant/debug",
            "sentences": [
                "set test light brightness to 1001%",
            ],
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot

    results = msg["result"]["results"]
    assert len(results) == 1
    assert not results[0]["match"]

    # Name matched, but brightness didn't
    assert results[0]["slots"] == {"name": "test light"}
    assert results[0]["unmatched_slots"] == {"brightness": 1001}


async def test_ws_hass_agent_debug_custom_sentence(
    hass: HomeAssistant,
    init_components,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test homeassistant agent debug websocket command with a custom sentence."""
    # Expecting testing_config/custom_sentences/en/beer.yaml
    intent.async_register(hass, OrderBeerIntentHandler())

    client = await hass_ws_client(hass)

    # Brightness is in range (0-100)
    await client.send_json_auto_id(
        {
            "type": "conversation/agent/homeassistant/debug",
            "sentences": [
                "I'd like to order a lager, please.",
            ],
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot

    debug_results = msg["result"].get("results", [])
    assert len(debug_results) == 1
    assert debug_results[0].get("match")
    assert debug_results[0].get("source") == "custom"
    assert debug_results[0].get("file") == "en/beer.yaml"


async def test_ws_hass_agent_debug_sentence_trigger(
    hass: HomeAssistant,
    init_components,
    hass_ws_client: WebSocketGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test homeassistant agent debug websocket command with a sentence trigger."""
    calls = async_mock_service(hass, "test", "automation")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": ["hello", "hello[ world]"],
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"data": "{{ trigger }}"},
                },
            }
        },
    )

    client = await hass_ws_client(hass)

    # Use trigger sentence
    await client.send_json_auto_id(
        {
            "type": "conversation/agent/homeassistant/debug",
            "sentences": ["hello world"],
        }
    )
    await hass.async_block_till_done()

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot

    debug_results = msg["result"].get("results", [])
    assert len(debug_results) == 1
    assert debug_results[0].get("match")
    assert debug_results[0].get("source") == "trigger"
    assert debug_results[0].get("sentence_template") == "hello[ world]"

    # Trigger should not have been executed
    assert len(calls) == 0
