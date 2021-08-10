"""The tests for the Conversation component."""
import pytest

from homeassistant.components import conversation
from homeassistant.core import DOMAIN as HASS_DOMAIN, Context
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import async_mock_intent, async_mock_service


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

    assert resp.status == 200
    data = await resp.json()

    assert data == {
        "card": {
            "simple": {"content": "You chose a Grolsch.", "title": "Beer ordered"}
        },
        "speech": {"plain": {"extra_data": None, "speech": "I've ordered a Grolsch!"}},
    }


@pytest.mark.parametrize("sentence", ("turn on kitchen", "turn kitchen on"))
async def test_turn_on_intent(hass, sentence):
    """Test calling the turn on intent."""
    result = await async_setup_component(hass, "homeassistant", {})
    assert result

    result = await async_setup_component(hass, "conversation", {})
    assert result

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
async def test_turn_off_intent(hass, sentence):
    """Test calling the turn on intent."""
    result = await async_setup_component(hass, "homeassistant", {})
    assert result

    result = await async_setup_component(hass, "conversation", {})
    assert result

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
async def test_toggle_intent(hass, sentence):
    """Test calling the turn on intent."""
    result = await async_setup_component(hass, "homeassistant", {})
    assert result

    result = await async_setup_component(hass, "conversation", {})
    assert result

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


async def test_http_api(hass, hass_client):
    """Test the HTTP conversation API."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})

    client = await hass_client()
    hass.states.async_set("light.kitchen", "off")
    calls = async_mock_service(hass, HASS_DOMAIN, "turn_on")

    resp = await client.post(
        "/api/conversation/process", json={"text": "Turn the kitchen on"}
    )
    assert resp.status == 200

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == HASS_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": "light.kitchen"}


async def test_http_api_wrong_data(hass, hass_client):
    """Test the HTTP conversation API."""
    result = await async_setup_component(hass, "homeassistant", {})
    assert result

    result = await async_setup_component(hass, "conversation", {})
    assert result

    client = await hass_client()

    resp = await client.post("/api/conversation/process", json={"text": 123})
    assert resp.status == 400

    resp = await client.post("/api/conversation/process", json={})
    assert resp.status == 400


async def test_custom_agent(hass, hass_client, hass_admin_user):
    """Test a custom conversation agent."""

    calls = []

    class MyAgent(conversation.AbstractConversationAgent):
        """Test Agent."""

        async def async_process(self, text, context, conversation_id):
            """Process some text."""
            calls.append((text, context, conversation_id))
            response = intent.IntentResponse()
            response.async_set_speech("Test response")
            return response

    conversation.async_set_agent(hass, MyAgent())

    assert await async_setup_component(hass, "conversation", {})

    client = await hass_client()

    resp = await client.post(
        "/api/conversation/process",
        json={"text": "Test Text", "conversation_id": "test-conv-id"},
    )
    assert resp.status == 200
    assert await resp.json() == {
        "card": {},
        "speech": {"plain": {"extra_data": None, "speech": "Test response"}},
    }

    assert len(calls) == 1
    assert calls[0][0] == "Test Text"
    assert calls[0][1].user_id == hass_admin_user.id
    assert calls[0][2] == "test-conv-id"
