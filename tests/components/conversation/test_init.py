"""The tests for the Conversation component."""
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.cover import SERVICE_OPEN_COVER
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    area_registry,
    device_registry,
    entity_registry,
    intent,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockUser, async_mock_service
from tests.typing import ClientSessionGenerator, WebSocketGenerator

AGENT_ID_OPTIONS = [None, conversation.AgentManager.HOME_ASSISTANT_AGENT]


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


@pytest.mark.parametrize("agent_id", AGENT_ID_OPTIONS)
async def test_http_processing_intent(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    agent_id,
) -> None:
    """Test processing intent via HTTP API."""
    # Add an alias
    entities = entity_registry.async_get(hass)
    entities.async_get_or_create("light", "demo", "1234", suggested_object_id="kitchen")
    entities.async_update_entity("light.kitchen", aliases={"my cool light"})
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

    assert data == {
        "response": {
            "response_type": "action_done",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Turned on light",
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


async def test_http_processing_intent_target_ha_agent(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    mock_agent,
) -> None:
    """Test processing intent can be processed via HTTP API with picking agent."""
    # Add an alias
    entities = entity_registry.async_get(hass)
    entities.async_get_or_create("light", "demo", "1234", suggested_object_id="kitchen")
    entities.async_update_entity("light.kitchen", aliases={"my cool light"})
    hass.states.async_set("light.kitchen", "off")

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process",
        json={"text": "turn on my cool light", "agent_id": "homeassistant"},
    )

    assert resp.status == HTTPStatus.OK
    assert len(calls) == 1
    data = await resp.json()

    assert data == {
        "response": {
            "response_type": "action_done",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Turned on light",
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


async def test_http_processing_intent_entity_added(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
) -> None:
    """Test processing intent via HTTP API with entities added later.

    We want to ensure that adding an entity later busts the cache
    so that the new entity is available as well as any aliases.
    """
    er = entity_registry.async_get(hass)
    er.async_get_or_create("light", "demo", "1234", suggested_object_id="kitchen")
    er.async_update_entity("light.kitchen", aliases={"my cool light"})
    hass.states.async_set("light.kitchen", "off")

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on my cool light"}
    )

    assert resp.status == HTTPStatus.OK
    assert len(calls) == 1
    data = await resp.json()

    assert data == {
        "response": {
            "response_type": "action_done",
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Turned on light",
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

    # Add an alias
    er.async_get_or_create("light", "demo", "5678", suggested_object_id="late")
    hass.states.async_set("light.late", "off", {"friendly_name": "friendly light"})

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on friendly light"}
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
                    "speech": "Turned on light",
                }
            },
            "language": hass.config.language,
            "data": {
                "targets": [],
                "success": [
                    {"id": "light.late", "name": "friendly light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    # Now add an alias
    er.async_update_entity("light.late", aliases={"late added light"})

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on late added light"}
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
                    "speech": "Turned on light",
                }
            },
            "language": hass.config.language,
            "data": {
                "targets": [],
                "success": [
                    {"id": "light.late", "name": "friendly light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    # Now delete the entity
    er.async_remove("light.late")

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on late added light"}
    )

    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == {
        "conversation_id": None,
        "response": {
            "card": {},
            "data": {"code": "no_intent_match"},
            "language": hass.config.language,
            "response_type": "error",
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Sorry, I couldn't understand that",
                }
            },
        },
    }


@pytest.mark.parametrize("agent_id", AGENT_ID_OPTIONS)
@pytest.mark.parametrize("sentence", ("turn on kitchen", "turn kitchen on"))
async def test_turn_on_intent(
    hass: HomeAssistant, init_components, sentence, agent_id
) -> None:
    """Test calling the turn on intent."""
    hass.states.async_set("light.kitchen", "off")
    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    data = {conversation.ATTR_TEXT: sentence}
    if agent_id is not None:
        data[conversation.ATTR_AGENT_ID] = agent_id
    await hass.services.async_call("conversation", "process", data)
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.kitchen"]}


@pytest.mark.parametrize("sentence", ("turn off kitchen", "turn kitchen off"))
async def test_turn_off_intent(hass: HomeAssistant, init_components, sentence) -> None:
    """Test calling the turn on intent."""
    hass.states.async_set("light.kitchen", "on")
    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_off")

    await hass.services.async_call(
        "conversation", "process", {conversation.ATTR_TEXT: sentence}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_off"
    assert call.data == {"entity_id": ["light.kitchen"]}


async def test_http_api_no_match(
    hass: HomeAssistant, init_components, hass_client: ClientSessionGenerator
) -> None:
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
                    "speech": "Sorry, I couldn't understand that",
                    "extra_data": None,
                },
            },
            "language": hass.config.language,
            "data": {"code": "no_intent_match"},
        },
        "conversation_id": None,
    }


async def test_http_api_handle_failure(
    hass: HomeAssistant, init_components, hass_client: ClientSessionGenerator
) -> None:
    """Test the HTTP conversation API with an error during handling."""
    client = await hass_client()

    hass.states.async_set("light.kitchen", "off")

    # Raise an error during intent handling
    def async_handle_error(*args, **kwargs):
        raise intent.IntentHandleError()

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
                    "speech": "An unexpected error occurred while handling the intent",
                }
            },
            "language": hass.config.language,
            "data": {
                "code": "failed_to_handle",
            },
        },
        "conversation_id": None,
    }


async def test_http_api_unexpected_failure(
    hass: HomeAssistant, init_components, hass_client: ClientSessionGenerator
) -> None:
    """Test the HTTP conversation API with an unexpected error during handling."""
    client = await hass_client()

    hass.states.async_set("light.kitchen", "off")

    # Raise an "unexpected" error during intent handling
    def async_handle_error(*args, **kwargs):
        raise intent.IntentUnexpectedError()

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
                    "speech": "An unexpected error occurred while handling the intent",
                }
            },
            "language": hass.config.language,
            "data": {
                "code": "unknown",
            },
        },
        "conversation_id": None,
    }


async def test_http_api_wrong_data(
    hass: HomeAssistant, init_components, hass_client: ClientSessionGenerator
) -> None:
    """Test the HTTP conversation API."""
    client = await hass_client()

    resp = await client.post("/api/conversation/process", json={"text": 123})
    assert resp.status == HTTPStatus.BAD_REQUEST

    resp = await client.post("/api/conversation/process", json={})
    assert resp.status == HTTPStatus.BAD_REQUEST


@pytest.mark.parametrize("agent_id", (None, "mock-entry"))
async def test_custom_agent(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    mock_agent,
    agent_id,
) -> None:
    """Test a custom conversation agent."""
    assert await async_setup_component(hass, "conversation", {})

    client = await hass_client()

    data = {
        "text": "Test Text",
        "conversation_id": "test-conv-id",
        "language": "test-language",
    }
    if agent_id is not None:
        data["agent_id"] = agent_id

    resp = await client.post("/api/conversation/process", json=data)
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
    assert mock_agent.calls[0].text == "Test Text"
    assert mock_agent.calls[0].context.user_id == hass_admin_user.id
    assert mock_agent.calls[0].conversation_id == "test-conv-id"
    assert mock_agent.calls[0].language == "test-language"

    conversation.async_unset_agent(
        hass, hass.config_entries.async_get_entry(mock_agent.agent_id)
    )


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
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, payload
) -> None:
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
                    "speech": "Sorry, I couldn't understand that",
                }
            },
            "language": payload.get("language", hass.config.language),
            "data": {"code": "no_intent_match"},
        },
        "conversation_id": None,
    }


@pytest.mark.parametrize("agent_id", AGENT_ID_OPTIONS)
async def test_ws_prepare(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, agent_id
) -> None:
    """Test the Websocket prepare conversation API."""
    assert await async_setup_component(hass, "conversation", {})
    agent = await conversation._get_agent_manager(hass).async_get_agent()
    assert isinstance(agent, conversation.DefaultAgent)

    # No intents should be loaded yet
    assert not agent._lang_intents.get(hass.config.language)

    client = await hass_ws_client(hass)

    msg = {
        "id": 5,
        "type": "conversation/prepare",
    }
    if agent_id is not None:
        msg["agent_id"] = agent_id
    await client.send_json(msg)

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["id"] == 5

    # Intents should now be load
    assert agent._lang_intents.get(hass.config.language)


async def test_custom_sentences(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test custom sentences with a custom intent."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})

    # Expecting testing_config/custom_sentences/en/beer.yaml
    intent.async_register(hass, OrderBeerIntentHandler())

    # Don't use "en" to test loading custom sentences with language variants.
    language = "en-us"

    # Invoke intent via HTTP API
    client = await hass_client()
    for beer_style in ("stout", "lager"):
        resp = await client.post(
            "/api/conversation/process",
            json={
                "text": f"I'd like to order a {beer_style}, please",
                "language": language,
            },
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
                "language": language,
                "response_type": "action_done",
                "data": {
                    "targets": [],
                    "success": [],
                    "failed": [],
                },
            },
            "conversation_id": None,
        }


async def test_custom_sentences_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_admin_user: MockUser
) -> None:
    """Test custom sentences with a custom intent in config."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(
        hass,
        "conversation",
        {"conversation": {"intents": {"StealthMode": ["engage stealth mode"]}}},
    )
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(
        hass,
        "intent_script",
        {
            "intent_script": {
                "StealthMode": {"speech": {"text": "Stealth mode engaged"}}
            }
        },
    )

    # Invoke intent via HTTP API
    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process",
        json={"text": "engage stealth mode"},
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data == {
        "response": {
            "card": {},
            "speech": {
                "plain": {
                    "extra_data": None,
                    "speech": "Stealth mode engaged",
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


async def test_prepare_reload(hass: HomeAssistant) -> None:
    """Test calling the reload service."""
    language = hass.config.language
    assert await async_setup_component(hass, "conversation", {})

    # Load intents
    agent = await conversation._get_agent_manager(hass).async_get_agent()
    assert isinstance(agent, conversation.DefaultAgent)
    await agent.async_prepare(language)

    # Confirm intents are loaded
    assert agent._lang_intents.get(language)

    # Clear cache
    await hass.services.async_call("conversation", "reload", {})
    await hass.async_block_till_done()

    # Confirm intent cache is cleared
    assert not agent._lang_intents.get(language)


async def test_prepare_fail(hass: HomeAssistant) -> None:
    """Test calling prepare with a non-existent language."""
    assert await async_setup_component(hass, "conversation", {})

    # Load intents
    agent = await conversation._get_agent_manager(hass).async_get_agent()
    assert isinstance(agent, conversation.DefaultAgent)
    await agent.async_prepare("not-a-language")

    # Confirm no intents were loaded
    assert not agent._lang_intents.get("not-a-language")


async def test_language_region(hass: HomeAssistant, init_components) -> None:
    """Test calling the turn on intent."""
    hass.states.async_set("light.kitchen", "off")
    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    # Add fake region
    language = f"{hass.config.language}-YZ"
    await hass.services.async_call(
        "conversation",
        "process",
        {
            conversation.ATTR_TEXT: "turn on the kitchen",
            conversation.ATTR_LANGUAGE: language,
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.kitchen"]}


async def test_reload_on_new_component(hass: HomeAssistant) -> None:
    """Test intents being reloaded when a new component is loaded."""
    language = hass.config.language
    assert await async_setup_component(hass, "conversation", {})

    # Load intents
    agent = await conversation._get_agent_manager(hass).async_get_agent()
    assert isinstance(agent, conversation.DefaultAgent)
    await agent.async_prepare()

    lang_intents = agent._lang_intents.get(language)
    assert lang_intents is not None
    loaded_components = set(lang_intents.loaded_components)

    # Load another component
    assert await async_setup_component(hass, "light", {})

    # Intents should reload
    await agent.async_prepare()
    lang_intents = agent._lang_intents.get(language)
    assert lang_intents is not None

    assert {"light"} == (lang_intents.loaded_components - loaded_components)


async def test_non_default_response(hass: HomeAssistant, init_components) -> None:
    """Test intent response that is not the default."""
    hass.states.async_set("cover.front_door", "closed")
    calls = async_mock_service(hass, "cover", SERVICE_OPEN_COVER)

    agent = await conversation._get_agent_manager(hass).async_get_agent()
    assert isinstance(agent, conversation.DefaultAgent)

    result = await agent.async_process(
        conversation.ConversationInput(
            text="open the front door",
            context=Context(),
            conversation_id=None,
            language=hass.config.language,
        )
    )
    assert len(calls) == 1
    assert result.response.speech["plain"]["speech"] == "Opened"


async def test_turn_on_area(hass: HomeAssistant, init_components) -> None:
    """Test turning on an area."""
    er = entity_registry.async_get(hass)
    dr = device_registry.async_get(hass)
    ar = area_registry.async_get(hass)
    entry = MockConfigEntry(domain="test")

    device = dr.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    kitchen_area = ar.async_create("kitchen")
    dr.async_update_device(device.id, area_id=kitchen_area.id)

    er.async_get_or_create("light", "demo", "1234", suggested_object_id="stove")
    er.async_update_entity(
        "light.stove", aliases={"my stove light"}, area_id=kitchen_area.id
    )
    hass.states.async_set("light.stove", "off")

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "turn on lights in the kitchen"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.stove"]}

    basement_area = ar.async_create("basement")
    dr.async_update_device(device.id, area_id=basement_area.id)
    er.async_update_entity("light.stove", area_id=basement_area.id)
    calls.clear()

    # Test that the area is updated
    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "turn on lights in the kitchen"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0

    # Test the new area works
    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "turn on lights in the basement"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.stove"]}


async def test_light_area_same_name(hass: HomeAssistant, init_components) -> None:
    """Test turning on a light with the same name as an area."""
    entities = entity_registry.async_get(hass)
    devices = device_registry.async_get(hass)
    areas = area_registry.async_get(hass)
    entry = MockConfigEntry(domain="test")

    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    kitchen_area = areas.async_create("kitchen")
    devices.async_update_device(device.id, area_id=kitchen_area.id)

    kitchen_light = entities.async_get_or_create(
        "light", "demo", "1234", original_name="kitchen light"
    )
    entities.async_update_entity(kitchen_light.entity_id, area_id=kitchen_area.id)
    hass.states.async_set(
        kitchen_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )

    ceiling_light = entities.async_get_or_create(
        "light", "demo", "5678", original_name="ceiling light"
    )
    entities.async_update_entity(ceiling_light.entity_id, area_id=kitchen_area.id)
    hass.states.async_set(
        ceiling_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "ceiling light"}
    )

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    await hass.services.async_call(
        "conversation",
        "process",
        {conversation.ATTR_TEXT: "turn on kitchen light"},
    )
    await hass.async_block_till_done()

    # Should only turn on one light instead of all lights in the kitchen
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": [kitchen_light.entity_id]}


async def test_agent_id_validator_invalid_agent(hass: HomeAssistant) -> None:
    """Test validating agent id."""
    with pytest.raises(vol.Invalid):
        conversation.agent_id_validator("invalid_agent")

    conversation.agent_id_validator(conversation.AgentManager.HOME_ASSISTANT_AGENT)


async def test_get_agent_list(
    hass: HomeAssistant, init_components, mock_agent, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting agent info."""
    client = await hass_ws_client(hass)

    await client.send_json({"id": 5, "type": "conversation/agent/list"})

    msg = await client.receive_json()
    assert msg["id"] == 5
    assert msg["type"] == "result"
    assert msg["success"]
    assert msg["result"] == {
        "agents": [
            {"id": "homeassistant", "name": "Home Assistant"},
            {"id": "mock-entry", "name": "Mock Title"},
        ],
        "default_agent": "mock-entry",
    }
