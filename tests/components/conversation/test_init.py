"""The tests for the Conversation component."""
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.cover import SERVICE_OPEN_COVER
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    intent,
)
from homeassistant.setup import async_setup_component

from . import expose_entity, expose_new

from tests.common import MockConfigEntry, MockUser, async_mock_service
from tests.typing import ClientSessionGenerator, WebSocketGenerator

AGENT_ID_OPTIONS = [None, conversation.HOME_ASSISTANT_AGENT]


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
    entity_registry: er.EntityRegistry,
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
    entity_registry: er.EntityRegistry,
) -> None:
    """Test processing intent can be processed via HTTP API with picking agent."""
    # Add an alias
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity("light.kitchen", aliases={"my cool light"})
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


async def test_http_processing_intent_entity_added_removed(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test processing intent via HTTP API with entities added later.

    We want to ensure that adding an entity later busts the cache
    so that the new entity is available as well as any aliases.
    """
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    entity_registry.async_update_entity("light.kitchen", aliases={"my cool light"})
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

    # Add an entity
    entity_registry.async_get_or_create(
        "light", "demo", "5678", suggested_object_id="late"
    )
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
    entity_registry.async_update_entity("light.late", aliases={"late added light"})

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
    hass.states.async_remove("light.late")

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


async def test_http_processing_intent_alias_added_removed(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test processing intent via HTTP API with aliases added later.

    We want to ensure that adding an alias later busts the cache
    so that the new alias is available.
    """
    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="kitchen"
    )
    hass.states.async_set("light.kitchen", "off", {"friendly_name": "kitchen light"})

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    # Add an alias
    entity_registry.async_update_entity("light.kitchen", aliases={"late added alias"})

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on late added alias"}
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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    # Now remove the alieas
    entity_registry.async_update_entity("light.kitchen", aliases={})

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on late added alias"}
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


async def test_http_processing_intent_entity_renamed(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
) -> None:
    """Test processing intent via HTTP API with entities renamed later.

    We want to ensure that renaming an entity later busts the cache
    so that the new name is used.
    """
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    entity = platform.MockLight("kitchen light", "on")
    entity._attr_unique_id = "1234"
    entity.entity_id = "light.kitchen"
    platform.ENTITIES.append(entity)
    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    # Rename the entity
    entity_registry.async_update_entity("light.kitchen", name="renamed light")
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on renamed light"}
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
                    {"id": "light.kitchen", "name": "renamed light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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

    # Now clear the custom name
    entity_registry.async_update_entity("light.kitchen", name=None)
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on renamed light"}
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


async def test_http_processing_intent_entity_exposed(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
) -> None:
    """Test processing intent via HTTP API with manual expose.

    We want to ensure that manually exposing an entity later busts the cache
    so that the new setting is used.
    """
    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    entity = platform.MockLight("kitchen light", "on")
    entity._attr_unique_id = "1234"
    entity.entity_id = "light.kitchen"
    platform.ENTITIES.append(entity)
    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )
    await hass.async_block_till_done()
    entity_registry.async_update_entity("light.kitchen", aliases={"my cool light"})

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    # Unexpose the entity
    expose_entity(hass, "light.kitchen", False)
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on my cool light"}
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

    # Now expose the entity
    expose_entity(hass, "light.kitchen", True)
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }

    client = await hass_client()
    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on my cool light"}
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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }


async def test_http_processing_intent_conversion_not_expose_new(
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    entity_registry: er.EntityRegistry,
    enable_custom_integrations: None,
) -> None:
    """Test processing intent via HTTP API when not exposing new entities."""
    # Disable exposing new entities to the default agent
    expose_new(hass, False)

    platform = getattr(hass.components, "test.light")
    platform.init(empty=True)

    entity = platform.MockLight("kitchen light", "on")
    entity._attr_unique_id = "1234"
    entity.entity_id = "light.kitchen"
    platform.ENTITIES.append(entity)
    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: [{"platform": "test"}]},
    )
    await hass.async_block_till_done()

    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")
    client = await hass_client()

    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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

    # Expose the entity
    expose_entity(hass, "light.kitchen", True)
    await hass.async_block_till_done()

    resp = await client.post(
        "/api/conversation/process", json={"text": "turn on kitchen light"}
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
                    {"id": "light.kitchen", "name": "kitchen light", "type": "entity"}
                ],
                "failed": [],
            },
        },
        "conversation_id": None,
    }


@pytest.mark.parametrize("agent_id", AGENT_ID_OPTIONS)
@pytest.mark.parametrize("sentence", ("turn on kitchen", "turn kitchen on"))
async def test_turn_on_intent(
    hass: HomeAssistant, init_components, sentence, agent_id, snapshot
) -> None:
    """Test calling the turn on intent."""
    hass.states.async_set("light.kitchen", "off")
    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    data = {conversation.ATTR_TEXT: sentence}
    if agent_id is not None:
        data[conversation.ATTR_AGENT_ID] = agent_id
    result = await hass.services.async_call(
        "conversation",
        "process",
        data,
        blocking=True,
        return_response=True,
    )

    assert len(calls) == 1
    call = calls[0]
    assert call.domain == LIGHT_DOMAIN
    assert call.service == "turn_on"
    assert call.data == {"entity_id": ["light.kitchen"]}

    assert result == snapshot


async def test_service_fails(hass: HomeAssistant, init_components) -> None:
    """Test calling the turn on intent."""
    with pytest.raises(HomeAssistantError), patch(
        "homeassistant.components.conversation.async_converse",
        side_effect=intent.IntentHandleError,
    ):
        await hass.services.async_call(
            "conversation",
            "process",
            {"text": "bla"},
            blocking=True,
        )


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
    hass: HomeAssistant,
    init_components,
    hass_client: ClientSessionGenerator,
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


async def test_custom_agent(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    mock_agent,
) -> None:
    """Test a custom conversation agent."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "intent", {})

    client = await hass_client()

    data = {
        "text": "Test Text",
        "conversation_id": "test-conv-id",
        "language": "test-language",
        "agent_id": mock_agent.agent_id,
    }

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
    assert await async_setup_component(hass, "homeassistant", {})
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
    assert await async_setup_component(hass, "homeassistant", {})
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
    assert await async_setup_component(hass, "homeassistant", {})
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
    assert await async_setup_component(hass, "homeassistant", {})
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
    assert await async_setup_component(hass, "homeassistant", {})
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
            device_id=None,
            language=hass.config.language,
        )
    )
    assert len(calls) == 1
    assert result.response.speech["plain"]["speech"] == "Opened"


async def test_turn_on_area(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turning on an area."""
    entry = MockConfigEntry(domain="test")

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    kitchen_area = area_registry.async_create("kitchen")
    device_registry.async_update_device(device.id, area_id=kitchen_area.id)

    entity_registry.async_get_or_create(
        "light", "demo", "1234", suggested_object_id="stove"
    )
    entity_registry.async_update_entity(
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

    basement_area = area_registry.async_create("basement")
    device_registry.async_update_device(device.id, area_id=basement_area.id)
    entity_registry.async_update_entity("light.stove", area_id=basement_area.id)
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


async def test_light_area_same_name(
    hass: HomeAssistant,
    init_components,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test turning on a light with the same name as an area."""
    entry = MockConfigEntry(domain="test")

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    kitchen_area = area_registry.async_create("kitchen")
    device_registry.async_update_device(device.id, area_id=kitchen_area.id)

    kitchen_light = entity_registry.async_get_or_create(
        "light", "demo", "1234", original_name="kitchen light"
    )
    entity_registry.async_update_entity(
        kitchen_light.entity_id, area_id=kitchen_area.id
    )
    hass.states.async_set(
        kitchen_light.entity_id, "off", attributes={ATTR_FRIENDLY_NAME: "kitchen light"}
    )

    ceiling_light = entity_registry.async_get_or_create(
        "light", "demo", "5678", original_name="ceiling light"
    )
    entity_registry.async_update_entity(
        ceiling_light.entity_id, area_id=kitchen_area.id
    )
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

    conversation.agent_id_validator(conversation.HOME_ASSISTANT_AGENT)


async def test_get_agent_list(
    hass: HomeAssistant,
    init_components,
    mock_agent,
    mock_agent_support_all,
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


async def test_get_agent_info(
    hass: HomeAssistant, init_components, mock_agent, snapshot: SnapshotAssertion
) -> None:
    """Test get agent info."""
    agent_info = conversation.async_get_agent_info(hass)
    # Test it's the default
    assert conversation.async_get_agent_info(hass, "homeassistant") == agent_info
    assert conversation.async_get_agent_info(hass, "homeassistant") == snapshot
    assert conversation.async_get_agent_info(hass, mock_agent.agent_id) == snapshot
    assert conversation.async_get_agent_info(hass, "not exist") is None

    # Test the name when config entry title is empty
    agent_entry = hass.config_entries.async_get_entry("mock-entry")
    hass.config_entries.async_update_entry(agent_entry, title="")

    agent_info = conversation.async_get_agent_info(hass)
    assert agent_info == snapshot


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
                "this will not match anything",  # null in results
            ],
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert msg["result"] == snapshot

    # Light state should not have been changed
    assert len(on_calls) == 0
    assert len(off_calls) == 0
