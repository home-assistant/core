"""The tests for the Conversation component."""

from http import HTTPStatus
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    ConversationInput,
    async_handle_intents,
    async_handle_sentence_triggers,
    default_agent,
)
from homeassistant.components.conversation.const import DATA_DEFAULT_ENTITY
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from . import MockAgent

from tests.common import MockUser, async_mock_service
from tests.typing import ClientSessionGenerator

AGENT_ID_OPTIONS = [
    None,
    # Old value of conversation.HOME_ASSISTANT_AGENT,
    "homeassistant",
    # Current value of conversation.HOME_ASSISTANT_AGENT,
    "conversation.home_assistant",
]


@pytest.mark.parametrize("agent_id", AGENT_ID_OPTIONS)
@pytest.mark.parametrize("sentence", ["turn on kitchen", "turn kitchen on"])
@pytest.mark.parametrize("conversation_id", ["my_new_conversation", None])
async def test_turn_on_intent(
    hass: HomeAssistant,
    init_components,
    conversation_id,
    sentence,
    agent_id,
    snapshot: SnapshotAssertion,
) -> None:
    """Test calling the turn on intent."""
    hass.states.async_set("light.kitchen", "off")
    calls = async_mock_service(hass, LIGHT_DOMAIN, "turn_on")

    data = {conversation.ATTR_TEXT: sentence}
    if agent_id is not None:
        data[conversation.ATTR_AGENT_ID] = agent_id
    if conversation_id is not None:
        data[conversation.ATTR_CONVERSATION_ID] = conversation_id
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
    with (
        pytest.raises(HomeAssistantError),
        patch(
            "homeassistant.components.conversation.async_converse",
            side_effect=intent.IntentHandleError,
        ),
    ):
        await hass.services.async_call(
            "conversation",
            "process",
            {"text": "bla"},
            blocking=True,
        )


@pytest.mark.parametrize("sentence", ["turn off kitchen", "turn kitchen off"])
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


@pytest.mark.usefixtures("init_components")
async def test_custom_agent(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    mock_conversation_agent: MockAgent,
    snapshot: SnapshotAssertion,
) -> None:
    """Test a custom conversation agent."""
    client = await hass_client()

    data = {
        "text": "Test Text",
        "conversation_id": "test-conv-id",
        "language": "test-language",
        "agent_id": mock_conversation_agent.agent_id,
    }

    resp = await client.post("/api/conversation/process", json=data)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data == snapshot
    assert data["response"]["response_type"] == "action_done"
    assert data["response"]["speech"]["plain"]["speech"] == "Test response"
    assert data["conversation_id"] == "test-conv-id"

    assert len(mock_conversation_agent.calls) == 1
    assert mock_conversation_agent.calls[0].text == "Test Text"
    assert mock_conversation_agent.calls[0].context.user_id == hass_admin_user.id
    assert mock_conversation_agent.calls[0].conversation_id == "test-conv-id"
    assert mock_conversation_agent.calls[0].language == "test-language"

    conversation.async_unset_agent(
        hass, hass.config_entries.async_get_entry(mock_conversation_agent.agent_id)
    )


async def test_prepare_reload(hass: HomeAssistant, init_components) -> None:
    """Test calling the reload service."""
    language = hass.config.language

    # Load intents
    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)
    await agent.async_prepare(language)

    # Confirm intents are loaded
    assert agent._lang_intents.get(language)

    # Try to clear for a different language
    await hass.services.async_call("conversation", "reload", {"language": "elvish"})
    await hass.async_block_till_done()

    # Confirm intents are still loaded
    assert agent._lang_intents.get(language)

    # Clear cache for all languages
    await hass.services.async_call("conversation", "reload", {})
    await hass.async_block_till_done()

    # Confirm intent cache is cleared
    assert not agent._lang_intents.get(language)


async def test_prepare_fail(hass: HomeAssistant) -> None:
    """Test calling prepare with a non-existent language."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})

    # Load intents
    agent = hass.data[DATA_DEFAULT_ENTITY]
    assert isinstance(agent, default_agent.DefaultAgent)
    await agent.async_prepare("not-a-language")

    # Confirm no intents were loaded
    assert agent._lang_intents.get("not-a-language") is default_agent.ERROR_SENTINEL


async def test_agent_id_validator_invalid_agent(
    hass: HomeAssistant, init_components
) -> None:
    """Test validating agent id."""
    with pytest.raises(vol.Invalid):
        conversation.agent_id_validator("invalid_agent")

    conversation.agent_id_validator(conversation.HOME_ASSISTANT_AGENT)
    conversation.agent_id_validator("conversation.home_assistant")


async def test_get_agent_info(
    hass: HomeAssistant,
    init_components,
    mock_conversation_agent: MockAgent,
    snapshot: SnapshotAssertion,
) -> None:
    """Test get agent info."""
    agent_info = conversation.async_get_agent_info(hass)
    # Test it's the default
    assert conversation.async_get_agent_info(hass, "homeassistant") == agent_info
    assert conversation.async_get_agent_info(hass, "homeassistant") == snapshot
    assert (
        conversation.async_get_agent_info(hass, mock_conversation_agent.agent_id)
        == snapshot
    )
    assert conversation.async_get_agent_info(hass, "not exist") is None

    # Test the name when config entry title is empty
    agent_entry = hass.config_entries.async_get_entry("mock-entry")
    hass.config_entries.async_update_entry(agent_entry, title="")

    agent_info = conversation.async_get_agent_info(hass)
    assert agent_info == snapshot


@pytest.mark.parametrize("agent_id", AGENT_ID_OPTIONS)
async def test_prepare_agent(
    hass: HomeAssistant,
    init_components,
    agent_id: str,
) -> None:
    """Test prepare agent."""
    with patch(
        "homeassistant.components.conversation.default_agent.DefaultAgent.async_prepare"
    ) as mock_prepare:
        await conversation.async_prepare_agent(hass, agent_id, "en")

    assert len(mock_prepare.mock_calls) == 1


@pytest.mark.parametrize(
    ("response_template", "expected_response"),
    [("response {{ trigger.device_id }}", "response 1234"), ("", "")],
)
async def test_async_handle_sentence_triggers(
    hass: HomeAssistant, response_template: str, expected_response: str
) -> None:
    """Test handling sentence triggers with async_handle_sentence_triggers."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {
                    "platform": "conversation",
                    "command": ["my trigger"],
                },
                "action": {
                    "set_conversation_response": response_template,
                },
            }
        },
    )

    # Device id will be available in response template
    device_id = "1234"
    actual_response = await async_handle_sentence_triggers(
        hass,
        ConversationInput(
            text="my trigger",
            context=Context(),
            conversation_id=None,
            agent_id=conversation.HOME_ASSISTANT_AGENT,
            device_id=device_id,
            language=hass.config.language,
        ),
    )
    assert actual_response == expected_response


async def test_async_handle_intents(hass: HomeAssistant) -> None:
    """Test handling registered intents with async_handle_intents."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "conversation", {})

    # Reuse custom sentences in test config to trigger default agent.
    class OrderBeerIntentHandler(intent.IntentHandler):
        intent_type = "OrderBeer"

        def __init__(self) -> None:
            super().__init__()
            self.was_handled = False

        async def async_handle(
            self, intent_obj: intent.Intent
        ) -> intent.IntentResponse:
            self.was_handled = True
            return intent_obj.create_response()

    handler = OrderBeerIntentHandler()
    intent.async_register(hass, handler)

    # Registered intent will be handled
    result = await async_handle_intents(
        hass,
        ConversationInput(
            text="I'd like to order a stout",
            context=Context(),
            agent_id=conversation.HOME_ASSISTANT_AGENT,
            conversation_id=None,
            device_id=None,
            language=hass.config.language,
        ),
    )
    assert result is not None
    assert result.intent is not None
    assert result.intent.intent_type == handler.intent_type
    assert handler.was_handled

    # No error messages, just None as a result
    result = await async_handle_intents(
        hass,
        ConversationInput(
            text="this sentence does not exist",
            agent_id=conversation.HOME_ASSISTANT_AGENT,
            context=Context(),
            conversation_id=None,
            device_id=None,
            language=hass.config.language,
        ),
    )
    assert result is None
