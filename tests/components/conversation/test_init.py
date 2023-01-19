"""The tests for the Conversation component."""
from http import HTTPStatus
from unittest.mock import ANY, patch

import pytest

from homeassistant.components import conversation
from homeassistant.core import DOMAIN as HASS_DOMAIN
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


class OrderBeerIntentHandler(intent.IntentHandler):
    """Handle OrderBeer intent."""

    intent_type = "OrderBeer"

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """Return speech response."""
        beer_style = intent_obj.slots["beer_style"]["value"]
        response = intent_obj.create_response()
        response.async_set_speech(f"You ordered a {beer_style}")
        return response


@pytest.fixture
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})


async def test_http_processing_intent(
    hass, init_components, hass_client, hass_admin_user
):
    """Test processing intent via HTTP API."""
    hass.states.async_set("light.kitchen", "on")
    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen"}
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "response_type": "action_done",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Turned kitchen on",
                }
            },
            "language": hass.config.language,
            "data": {
                "targets": [],
                "success": [
                    {"id": "light.kitchen", "name": "kitchen", "type": "entity"}
                ],
                "failed": [],
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

    # Shouldn't match any intents
    resp = await client.post("/api/conversation/process", json={"text": "do something"})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "response_type": "error",
            "card": {},
            "speech": {
                "plain": {
                    "speech": "Sorry, I didn't understand that",
                    "extra_data": None,
                },
            },
            "language": hass.config.language,
            "data": {"code": "no_intent_match"},
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


async def test_custom_agent(hass, hass_client, hass_admin_user, mock_agent):
    """Test a custom conversation agent."""
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

    assert len(mock_agent.calls) == 1
    assert mock_agent.calls[0][0] == "Test Text"
    assert mock_agent.calls[0][1].user_id == hass_admin_user.id
    assert mock_agent.calls[0][2] == "test-conv-id"
    assert mock_agent.calls[0][3] == "test-language"


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
    ],
)
async def test_ws_api(hass, hass_ws_client, payload):
    """Test the Websocket conversation API."""
    assert await async_setup_component(hass, "conversation", {})
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "conversation/process", **payload})

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == {
        "response": {
            "response_type": "error",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Sorry, I didn't understand that",
                }
            },
            "language": payload.get("language", hass.config.language),
            "data": {"code": "no_intent_match"},
        },
        "conversation_id": payload.get("conversation_id") or ANY,
    }


# pylint: disable=protected-access
async def test_ws_prepare(hass, hass_ws_client):
    """Test the Websocket prepare conversation API."""
    assert await async_setup_component(hass, "conversation", {})
    agent = await conversation._get_agent(hass)
    assert isinstance(agent, conversation.DefaultAgent)

    # No intents should be loaded yet
    assert not agent._lang_intents.get(hass.config.language)

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "conversation/prepare",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["id"] == 5

    # Intents should now be load
    assert agent._lang_intents.get(hass.config.language)


async def test_custom_sentences(hass, hass_client, hass_admin_user):
    """Test custom sentences with a custom intent."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})

    # Expecting testing_config/custom_sentences/en/beer.yaml
    intent.async_register(hass, OrderBeerIntentHandler())

    # Invoke intent via HTTP API
    client = await hass_client()
    for beer_style in ("stout", "lager"):
        resp = await client.post(
            "/api/conversation/process",
            json={"text": f"I'd like to order a {beer_style}, please"},
        )
        assert resp.status == HTTPStatus.OK
        data = await resp.json()

        assert data == {
            "response": {
                "card": {},
                "speech": {
                    "plain": {
                        "extra_data": None,
                        "speech": f"You ordered a {beer_style}",
                    }
                },
                "language": hass.config.language,
                "response_type": "action_done",
                "data": {
                    "targets": [],
                    "success": [],
                    "failed": [],
                },
            },
            "conversation_id": None,
        }


# pylint: disable=protected-access
async def test_prepare_reload(hass):
    """Test calling the reload service."""
    language = hass.config.language
    assert await async_setup_component(hass, "conversation", {})

    # Load intents
    agent = await conversation._get_agent(hass)
    assert isinstance(agent, conversation.DefaultAgent)
    await agent.async_prepare(language)

    # Confirm intents are loaded
    assert agent._lang_intents.get(language)

    # Clear cache
    await hass.services.async_call("conversation", "reload", {})
    await hass.async_block_till_done()

    # Confirm intent cache is cleared
    assert not agent._lang_intents.get(language)


# pylint: disable=protected-access
async def test_prepare_fail(hass):
    """Test calling prepare with a non-existent language."""
    assert await async_setup_component(hass, "conversation", {})

    # Load intents
    agent = await conversation._get_agent(hass)
    assert isinstance(agent, conversation.DefaultAgent)
    await agent.async_prepare("not-a-language")

    # Confirm no intents were loaded
    assert not agent._lang_intents.get("not-a-language")
