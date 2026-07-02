"""Tests for Open Responses conversation."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.open_responses.const import (
    CONF_BASE_URL,
    CONF_GENERATED_DEFAULT_SUBENTRY,
    DEFAULT_CONVERSATION_NAME,
    DOMAIN,
    RECOMMENDED_CONVERSATION_OPTIONS,
)
from homeassistant.components.open_responses.conversation import (
    OpenResponsesConversationEntity,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL, MATCH_ALL
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


def _mock_response_create(calls: list[dict[str, Any]], text: str) -> Any:
    """Return a response create mock."""

    async def stream_response() -> AsyncGenerator[dict[str, Any]]:
        yield {
            "type": "response.output_item.added",
            "item": {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "content": [],
                "status": "in_progress",
            },
        }
        yield {"type": "response.output_text.delta", "delta": text}
        yield {
            "type": "response.output_item.done",
            "item": {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
                "status": "completed",
            },
        }
        yield {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 1, "output_tokens": 1}},
        }

    async def create(**params: Any) -> AsyncGenerator[dict[str, Any]]:
        calls.append(deepcopy(params))
        return stream_response()

    return create


async def test_conversation_turn(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_init_component: None,
) -> None:
    """Test a conversation turn reaches the Open Responses client."""
    hass.states.async_set("light.kitchen", "on")
    async_expose_entity(hass, "conversation", "light.kitchen", True)

    calls: list[dict[str, Any]] = []
    with patch(
        "homeassistant.components.open_responses.client.AsyncOpenResponsesClient.create",
        new_callable=AsyncMock,
        side_effect=_mock_response_create(calls, "Hello from Open Responses"),
    ):
        result = await conversation.async_converse(
            hass,
            "hello",
            None,
            Context(),
            agent_id=mock_config_entry.entry_id,
        )

    assert result.response.speech["plain"]["speech"] == "Hello from Open Responses"
    assert calls[0]["input"][0]["role"] == "system"
    assert calls[0]["model"] == "open-responses-model"
    assert any(tool["name"] == "GetLiveContext" for tool in calls[0]["tools"])
    assert calls[0]["input"][-1] == {
        "type": "message",
        "role": "user",
        "content": "hello",
    }


async def test_only_generated_default_subentry_registers_entry_agent(
    hass: HomeAssistant,
) -> None:
    """Test custom subentries do not override the config-entry agent."""
    entry = MockConfigEntry(
        title="Open Responses",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1",
            CONF_MODEL: "open-responses-model",
        },
        subentries_data=[
            ConfigSubentryData(
                data={
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_GENERATED_DEFAULT_SUBENTRY: True,
                    CONF_MODEL: "open-responses-model",
                },
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    **RECOMMENDED_CONVERSATION_OPTIONS,
                    CONF_MODEL: "open-responses-model",
                },
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.open_responses.conversation.conversation.async_set_agent"
    ) as mock_set_agent:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

    assert mock_set_agent.call_count == 1
    assert mock_set_agent.call_args.args[1] is entry


async def test_setup_entry_skips_non_conversation_subentries(
    hass: HomeAssistant,
) -> None:
    """Test non-conversation subentries are ignored."""
    entry = MockConfigEntry(
        title="Open Responses",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
            CONF_BASE_URL: "https://example.local/v1",
            CONF_MODEL: "open-responses-model",
        },
        subentries_data=[
            ConfigSubentryData(
                data={},
                subentry_type="other",
                title="Other",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={CONF_MODEL: "open-responses-model"},
                subentry_type="conversation",
                title=DEFAULT_CONVERSATION_NAME,
                unique_id=None,
            ),
        ],
    )
    entry.add_to_hass(hass)
    added_entities = []

    def async_add_entities(entities, config_subentry_id=None):
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, async_add_entities)

    assert len(added_entities) == 1


def test_supported_languages(
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Open Responses conversation entities support all languages."""
    subentry = mock_config_entry.get_subentries_of_type("conversation")[0]
    entity = OpenResponsesConversationEntity(mock_config_entry, subentry)

    assert entity.supported_languages == MATCH_ALL


async def test_handle_message_returns_converse_error_result(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test LLM API setup errors are returned as conversation results."""
    subentry = mock_config_entry.get_subentries_of_type("conversation")[0]
    entity = OpenResponsesConversationEntity(mock_config_entry, subentry)
    user_input = conversation.ConversationInput(
        text="Turn on the light",
        context=Context(),
        conversation_id="conversation-id",
        device_id=None,
        language="en",
        satellite_id=None,
        agent_id=entity.entity_id or "",
    )
    chat_log = conversation.ChatLog(hass, user_input.conversation_id)
    error_response = intent.IntentResponse(language="en")
    converse_error = conversation.ConverseError(
        "failed", user_input.conversation_id or "", error_response
    )
    chat_log.async_provide_llm_data = AsyncMock(side_effect=converse_error)

    with patch.object(entity, "_async_handle_chat_log", AsyncMock()) as handle_chat_log:
        result = await entity._async_handle_message(user_input, chat_log)

    handle_chat_log.assert_not_called()
    assert result.response is error_response
