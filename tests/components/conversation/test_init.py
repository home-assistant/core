"""The tests for the Conversation component."""
from http import HTTPStatus
from unittest.mock import patch

import pytest

from homeassistant.components import conversation
from homeassistant.core import DOMAIN as HASS_DOMAIN, Context
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import async_mock_intent, async_mock_service


@pytest.fixture
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


async def test_calling_intent(hass):
    """Test calling an intent from a conversation."""
    intents = async_mock_intent(hass, "OrderBeer")

    result = await async_setup_component(hass, "homeassistant", {})
    assert result

    result = await async_setup_component(
        hass,
        "conversation",
        {"conversation": {"intents": {"OrderBeer": ["I would like the {type} beer"]}}},
    )
    assert result

    context = Context()

    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "I would like the Grolsch beer"},
        context=context,
    )
    await hass.async_block_till_done()

    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == "conversation"
    assert intent.intent_type == "OrderBeer"
    assert intent.slots == {"type": {"value": "Grolsch"}}
    assert intent.text_input == "I would like the Grolsch beer"
    assert intent.context is context


async def test_register_before_setup(hass):
    """Test calling an intent from a conversation."""
    intents = async_mock_intent(hass, "OrderBeer")

    hass.components.conversation.async_register("OrderBeer", ["A {type} beer, please"])

    result = await async_setup_component(
        hass,
        "conversation",
        {"conversation": {"intents": {"OrderBeer": ["I would like the {type} beer"]}}},
    )
    assert result

    await hass.services.async_call(
        "conversation", "process", {conversation.ATTR_TEXT: "A Grolsch beer, please"}
    )
    await hass.async_block_till_done()

    assert len(intents) == 1
    intent = intents[0]
    assert intent.platform == "conversation"
    assert intent.intent_type == "OrderBeer"
    assert intent.slots == {"type": {"value": "Grolsch"}}
    assert intent.text_input == "A Grolsch beer, please"

    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "I would like the Grolsch beer"},
    )
    await hass.async_block_till_done()

    assert len(intents) == 2
    intent = intents[1]
    assert intent.platform == "conversation"
    assert intent.intent_type == "OrderBeer"
    assert intent.slots == {"type": {"value": "Grolsch"}}
    assert intent.text_input == "I would like the Grolsch beer"


async def test_http_processing_intent(hass, hass_client, hass_admin_user):
    """Test processing intent via HTTP API."""

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "OrderBeer"

        async def async_handle(self, intent):
            """Handle the intent."""
            assert intent.context.user_id == hass_admin_user.id
            response = intent.create_response()
            response.async_set_speech(
                "I've ordered a {}!".format(intent.slots["type"]["value"])
            )
            response.async_set_card(
                "Beer ordered", "You chose a {}.".format(intent.slots["type"]["value"])
            )
            return response

    intent.async_register(hass, TestIntentHandler())

    result = await async_setup_component(
        hass,
        "conversation",
        {"conversation": {"intents": {"OrderBeer": ["I would like the {type} beer"]}}},
    )
    assert result

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "I would like the Grolsch beer"}
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "response_type": "action_done",
            "card": {
                "simple": {"content": "You chose a Grolsch.", "title": "Beer ordered"}
            },
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "I've ordered a Grolsch!",
                }
            },
            "language": hass.config.language,
            "data": {"targets": [], "success": [], "failed": []},
        },
        "conversation_id": None,
    }


async def test_http_failed_action(hass, hass_client, hass_admin_user):
    """Test processing intent via HTTP API with a partial completion."""

    class TestIntentHandler(intent.IntentHandler):
        """Test Intent Handler."""

        intent_type = "TurnOffLights"

        async def async_handle(self, handle_intent: intent.Intent):
            """Handle the intent."""
            response = handle_intent.create_response()
            area = handle_intent.slots["area"]["value"]

            # Mark some targets as successful, others as failed
            response.async_set_targets(
                intent_targets=[
                    intent.IntentResponseTarget(
                        type=intent.IntentResponseTargetType.AREA, name=area, id=area
                    )
                ]
            )
            response.async_set_results(
                success_results=[
                    intent.IntentResponseTarget(
                        type=intent.IntentResponseTargetType.ENTITY,
                        name="light1",
                        id="light.light1",
                    )
                ],
                failed_results=[
                    intent.IntentResponseTarget(
                        type=intent.IntentResponseTargetType.ENTITY,
                        name="light2",
                        id="light.light2",
                    )
                ],
            )

            return response

    intent.async_register(hass, TestIntentHandler())

    result = await async_setup_component(
        hass,
        "conversation",
        {
            "conversation": {
                "intents": {"TurnOffLights": ["turn off the lights in the {area}"]}
            }
        },
    )
    assert result

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "Turn off the lights in the kitchen"}
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "response_type": "action_done",
            "card": {},
            "speech": {},
            "language": hass.config.language,
            "data": {
                "targets": [{"type": "area", "id": "kitchen", "name": "kitchen"}],
                "success": [{"type": "entity", "id": "light.light1", "name": "light1"}],
                "failed": [{"type": "entity", "id": "light.light2", "name": "light2"}],
            },
        },
        "conversation_id": None,
    }


@pytest.mark.parametrize("sentence", ("turn on kitchen", "turn kitchen on"))
async def test_turn_on_intent(hass, init_components, sentence):
    """Test calling the turn on intent."""
    hass.states.async_set("light.kitchen", "off")
    calls = async_mock_service(hass, HASS_DOMAIN, "turn_on")

    await hass.services.async_call(
        "conversation", "process", {conversation.ATTR_TEXT: sentence}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": "light.kitchen"}


@pytest.mark.parametrize("sentence", ("turn off kitchen", "turn kitchen off"))
async def test_turn_off_intent(hass, init_components, sentence):
    """Test calling the turn on intent."""
    hass.states.async_set("light.kitchen", "on")
    calls = async_mock_service(hass, HASS_DOMAIN, "turn_off")

    await hass.services.async_call(
        "conversation", "process", {conversation.ATTR_TEXT: sentence}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == "turn_off"
    assert call.data == {"entity_id": "light.kitchen"}


@pytest.mark.parametrize("sentence", ("toggle kitchen", "kitchen toggle"))
async def test_toggle_intent(hass, init_components, sentence):
    """Test calling the turn on intent."""
    hass.states.async_set("light.kitchen", "on")
    calls = async_mock_service(hass, HASS_DOMAIN, "toggle")

    await hass.services.async_call(
        "conversation", "process", {conversation.ATTR_TEXT: sentence}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == "toggle"
    assert call.data == {"entity_id": "light.kitchen"}


async def test_http_api(hass, init_components, hass_client):
    """Test the HTTP conversation API."""
    client = await hass_client()
    hass.states.async_set("light.kitchen", "off")
    calls = async_mock_service(hass, HASS_DOMAIN, "turn_on")

    resp = await client.post(
        "/api/conversation/process", json={"text": "Turn the kitchen on"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "card": {},
            "speech": {"plain": {"extra_data": None, "speech": "Turned kitchen on"}},
            "language": hass.config.language,
            "response_type": "action_done",
            "data": {
                "targets": [],
                "success": [
                    {
                        "type": "entity",
                        "name": "kitchen",
                        "id": "light.kitchen",
                    },
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": "light.kitchen"}


async def test_http_api_no_match(hass, init_components, hass_client):
    """Test the HTTP conversation API with an intent match failure."""
    client = await hass_client()

    # Sentence should not match any intents
    resp = await client.post("/api/conversation/process", json={"text": "do something"})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Sorry, I didn't understand that",
                },
            },
            "language": hass.config.language,
            "response_type": "error",
            "data": {
                "code": "no_intent_match",
            },
        },
        "conversation_id": None,
    }


async def test_http_api_no_valid_targets(hass, init_components, hass_client):
    """Test the HTTP conversation API with no valid targets."""
    client = await hass_client()

    # No kitchen light
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on the kitchen"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "response_type": "error",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Unable to find an entity called kitchen",
                },
            },
            "language": hass.config.language,
            "data": {
                "code": "no_valid_targets",
            },
        },
        "conversation_id": None,
    }


async def test_http_api_handle_failure(hass, init_components, hass_client):
    """Test the HTTP conversation API with an error during handling."""
    client = await hass_client()

    hass.states.async_set("light.kitchen", "off")

    # Raise an "unexpected" error during intent handling
    def async_handle_error(*args, **kwargs):
        raise intent.IntentUnexpectedError(
            "Unexpected error turning on the kitchen light"
        )

    with patch("homeassistant.helpers.intent.async_handle", new=async_handle_error):
        resp = await client.post(
            "/api/conversation/process", json={"text": "turn on the kitchen"}
        )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "response_type": "error",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Unexpected error turning on the kitchen light",
                }
            },
            "language": hass.config.language,
            "data": {
                "code": "failed_to_handle",
            },
        },
        "conversation_id": None,
    }


async def test_http_api_wrong_data(hass, init_components, hass_client):
    """Test the HTTP conversation API."""
    client = await hass_client()

    resp = await client.post("/api/conversation/process", json={"text": 123})
    assert resp.status == HTTPStatus.BAD_REQUEST

    resp = await client.post("/api/conversation/process", json={})
    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_custom_agent(hass, hass_client, hass_admin_user):
    """Test a custom conversation agent."""

    calls = []

    class MyAgent(conversation.AbstractConversationAgent):
        """Test Agent."""

        async def async_process(self, text, context, conversation_id, language):
            """Process some text."""
            calls.append((text, context, conversation_id, language))
            response = intent.IntentResponse(language=language)
            response.async_set_speech("Test response")
            return conversation.ConversationResult(
                response=response, conversation_id=conversation_id
            )

    conversation.async_set_agent(hass, MyAgent())

    assert await async_setup_component(hass, "conversation", {})

    client = await hass_client()

    resp = await client.post(
        "/api/conversation/process",
        json={
            "text": "Test Text",
            "conversation_id": "test-conv-id",
            "language": "test-language",
        },
    )
    assert resp.status == HTTPStatus.OK
    assert await resp.json() == {
        "response": {
            "response_type": "action_done",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Test response",
                }
            },
            "language": "test-language",
            "data": {"targets": [], "success": [], "failed": []},
        },
        "conversation_id": "test-conv-id",
    }

    assert len(calls) == 1
    assert calls[0][0] == "Test Text"
    assert calls[0][1].user_id == hass_admin_user.id
    assert calls[0][2] == "test-conv-id"
    assert calls[0][3] == "test-language"
