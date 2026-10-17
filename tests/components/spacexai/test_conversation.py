"""Tests for SpaceXAI conversation."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from spacexai_subscription_client import (
    AuthenticationError,
    Completion,
    InvalidResponseError,
    Message,
    PermissionDeniedError,
    SpaceXAISubscriptionError,
    ToolCall,
    ToolResult,
)
from spacexai_subscription_client.const import TOKEN_URL

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.spacexai.const import MAX_TOOL_ITERATIONS
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import entity_registry as er, intent
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry, async_mock_service
from tests.components.conversation import MockChatLog, mock_chat_log  # noqa: F401
from tests.test_util.aiohttp import AiohttpClientMocker


def _text_response(text: str) -> Completion:
    """Return a client response containing assistant text."""
    return Completion(text, ())


def _tool_response() -> Completion:
    """Return a client response containing a Home Assistant tool call."""
    return Completion("", (ToolCall("call-1", "test_tool", {"param1": "call1"}),))


async def test_conversation_languages(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Advertise all conversation languages without generating a response."""
    await setup_integration(hass, mock_config_entry)

    assert (
        conversation.async_get_conversation_languages(hass, "conversation.grok") == "*"
    )
    mock_spacexai_subscription_client.async_create_response.assert_not_awaited()


async def test_setup_ignores_non_conversation_subentries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Only register conversation agents when an entry contains another subentry type."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data={CONF_MODEL: "other-model"},
            subentry_type="other",
            title="Other",
            unique_id=None,
        ),
    )

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert [
        (entry.entity_id, entry.config_subentry_id)
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    ] == [("conversation.grok", "conversation-subentry")]
    assert conversation.async_get_agent(hass, "conversation.grok") is not None
    mock_spacexai_subscription_client.async_create_response.assert_not_awaited()


async def test_conversation_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Return a Grok response through the Conversation platform."""
    mock_spacexai_subscription_client.async_create_response.return_value = (
        _text_response("Hello from Grok")
    )
    await setup_integration(hass, mock_config_entry)

    result = await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello from Grok"
    call = mock_spacexai_subscription_client.async_create_response.call_args.kwargs
    assert call["model"] == "grok-4.6"
    assert call["input_data"][0] == Message(
        "developer", mock_chat_log.content[0].content
    )
    assert mock_spacexai_subscription_client.async_create_response.call_args.args == (
        "access-token",
    )


async def test_home_assistant_tool_call(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Execute a Home Assistant tool and send its result back to Grok."""
    mock_chat_log.mock_tool_results({"call-1": "tool result"})
    mock_spacexai_subscription_client.async_create_response.side_effect = [
        _tool_response(),
        _text_response("The tool succeeded"),
    ]
    await setup_integration(hass, mock_config_entry_with_assist)

    result = await conversation.async_converse(
        hass,
        "Call the tool",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert mock_spacexai_subscription_client.async_create_response.await_count == 2
    second_input = (
        mock_spacexai_subscription_client.async_create_response.call_args_list[
            1
        ].kwargs["input_data"]
    )
    assert ToolResult("call-1", '"tool result"') in second_input


@pytest.mark.parametrize(
    ("exposed", "expected_targets", "expected_error"),
    [
        pytest.param(True, [["light.desk"]], None, id="exposed"),
        pytest.param(False, [], "MatchFailedError", id="not_exposed"),
    ],
)
async def test_assist_tool_respects_entity_exposure(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    exposed: bool,
    expected_targets: list[list[str]],
    expected_error: str | None,
) -> None:
    """Execute real Assist tools only for exposed entities."""
    assert await async_setup_component(hass, "intent", {})
    hass.states.async_set("light.desk", "off", {"friendly_name": "Desk"})
    hass.states.async_set("light.hall", "off", {"friendly_name": "Hall"})
    async_expose_entity(hass, conversation.DOMAIN, "light.desk", exposed)
    async_expose_entity(hass, conversation.DOMAIN, "light.hall", True)
    calls = async_mock_service(hass, "light", "turn_on")
    mock_spacexai_subscription_client.async_create_response.side_effect = [
        Completion(
            "",
            (ToolCall("call-1", "intent__HassTurnOn", {"name": "Desk"}),),
        ),
        _text_response("Request handled"),
    ]
    await setup_integration(hass, mock_config_entry_with_assist)

    result = await conversation.async_converse(
        hass, "Turn on Desk", None, Context(), agent_id="conversation.grok"
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert [call.data["entity_id"] for call in calls] == expected_targets
    requests = mock_spacexai_subscription_client.async_create_response.call_args_list
    assert len(requests) == 2
    tools = {tool.name: tool for tool in requests[0].kwargs["tools"]}
    assert tools["intent__HassTurnOn"].parameters["type"] == "object"
    tool_results = [
        item
        for item in requests[1].kwargs["input_data"]
        if isinstance(item, ToolResult)
    ]
    assert len(tool_results) == 1
    assert json.loads(tool_results[0].output).get("error") == expected_error


async def test_conversation_without_assist_does_not_offer_tools(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Keep provider requests tool-free when Assist access is disabled."""
    mock_spacexai_subscription_client.async_create_response.return_value = (
        _text_response("Hello")
    )
    await setup_integration(hass, mock_config_entry)

    result = await conversation.async_converse(
        hass, "Hello", None, Context(), agent_id="conversation.grok"
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert (
        mock_spacexai_subscription_client.async_create_response.call_args.kwargs[
            "tools"
        ]
        == []
    )


async def test_token_refresh_timeout_and_retry(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Report token endpoint timeouts and recover without discarding credentials."""
    await setup_integration(hass, mock_config_entry)
    expired_token = {**mock_config_entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": expired_token}
    )
    aioclient_mock.post(TOKEN_URL, exc=TimeoutError)

    result = await conversation.async_converse(
        hass, "Hello", None, Context(), agent_id="conversation.grok"
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == (
        "SpaceXAI returned an error while generating a response"
    )
    assert mock_config_entry.data["token"] == expired_token
    mock_spacexai_subscription_client.async_create_response.assert_not_awaited()

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    )
    mock_spacexai_subscription_client.async_create_response.return_value = (
        _text_response("Hello again")
    )

    result = await conversation.async_converse(
        hass, "Hello again", None, Context(), agent_id="conversation.grok"
    )

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello again"
    assert mock_config_entry.data["token"]["refresh_token"] == "new-refresh-token"
    assert mock_spacexai_subscription_client.async_create_response.await_count == 1
    assert mock_spacexai_subscription_client.async_create_response.call_args.args == (
        "new-access-token",
    )


async def test_token_refresh_cancellation(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Propagate cancellation during refresh without sending a provider request."""
    await setup_integration(hass, mock_config_entry)
    expired_token = {**mock_config_entry.data["token"], "expires_at": 0}
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, "token": expired_token}
    )
    aioclient_mock.post(TOKEN_URL, exc=asyncio.CancelledError)

    with pytest.raises(asyncio.CancelledError):
        await conversation.async_converse(
            hass, "Hello", None, Context(), agent_id="conversation.grok"
        )

    assert mock_config_entry.data["token"] == expired_token
    mock_spacexai_subscription_client.async_create_response.assert_not_awaited()


async def test_empty_response(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Return an intent error for an empty provider response."""
    mock_spacexai_subscription_client.async_create_response.side_effect = (
        InvalidResponseError
    )
    await setup_integration(hass, mock_config_entry)

    result = await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR


async def test_authentication_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Return an intent error when the OAuth access token is rejected."""
    mock_spacexai_subscription_client.async_create_response.side_effect = (
        AuthenticationError
    )
    await setup_integration(hass, mock_config_entry)

    result = await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )
    assert result.response.response_type is intent.IntentResponseType.ERROR


async def test_permission_denied_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Return an intent error when the account cannot use the subscription API."""
    mock_spacexai_subscription_client.async_create_response.side_effect = (
        PermissionDeniedError
    )
    await setup_integration(hass, mock_config_entry)

    result = await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR


async def test_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Return an intent error when the provider request fails."""
    mock_spacexai_subscription_client.async_create_response.side_effect = (
        SpaceXAISubscriptionError
    )
    await setup_integration(hass, mock_config_entry)

    result = await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR


async def test_llm_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Return the conversation error raised while preparing LLM data."""
    error_response = intent.IntentResponse(language="en")
    mock_chat_log.async_provide_llm_data = AsyncMock(
        side_effect=conversation.ConverseError(
            "failed", mock_chat_log.conversation_id or "", error_response
        )
    )
    await setup_integration(hass, mock_config_entry)

    result = await conversation.async_converse(
        hass,
        "Hello",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )

    assert result.response is error_response
    mock_spacexai_subscription_client.async_create_response.assert_not_awaited()


async def test_tool_iteration_limit(
    hass: HomeAssistant,
    mock_config_entry_with_assist: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Stop a provider that repeatedly requests tools."""
    mock_chat_log.mock_tool_results({"call-1": "tool result"})
    mock_spacexai_subscription_client.async_create_response.return_value = (
        _tool_response()
    )
    await setup_integration(hass, mock_config_entry_with_assist)

    result = await conversation.async_converse(
        hass,
        "Keep calling the tool",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert (
        mock_spacexai_subscription_client.async_create_response.await_count
        == MAX_TOOL_ITERATIONS
    )


async def test_attachments_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Reject attachments before making a provider request."""
    mock_chat_log.content.append(
        conversation.UserContent(
            "Describe this",
            [conversation.Attachment("media-id", "image/png", Path("image.png"))],
        )
    )
    await setup_integration(hass, mock_config_entry)

    result = await conversation.async_converse(
        hass,
        "Describe this",
        mock_chat_log.conversation_id,
        Context(),
        agent_id="conversation.grok",
    )

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == (
        "Attachments are not supported by this version of the SpaceXAI integration"
    )
    mock_spacexai_subscription_client.async_create_response.assert_not_awaited()
