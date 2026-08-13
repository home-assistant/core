"""Tests for SpaceXAI Conversation."""

import asyncio
import contextlib
import json
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun import freeze_time
import httpx
from openai import OpenAIError
from openai.types.responses import (
    ResponseInProgressEvent,
    ResponseOutputItemAddedEvent,
    ResponseOutputItemDoneEvent,
    ResponseOutputMessage,
    ResponseReasoningItem,
    ResponseReasoningSummaryTextDeltaEvent,
    ResponseRefusalDeltaEvent,
    ResponseStreamEvent,
    ResponseTextDeltaEvent,
)
from pydantic import ValidationError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import conversation
from homeassistant.components.conversation import trace
from homeassistant.components.spacexai.client import (
    AccountInfo,
    ModelInfo,
    ProviderSnapshot,
)
from homeassistant.components.spacexai.const import (
    CONF_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MODEL,
    MAX_TOOL_ITERATIONS,
)
from homeassistant.components.spacexai.conversation import SpaceXAIConversationEntity
from homeassistant.components.spacexai.entity import _format_tool, _stream_failure
from homeassistant.components.spacexai.errors import (
    ErrorContext,
    ModelNotEntitledError,
    Operation,
    PermanentProviderError,
    QuotaLimitedError,
    ReauthenticationRequiredError,
    SubscriptionNotEntitledError,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import (
    CONF_LLM_HASS_API,
    CONF_MODEL,
    CONF_PROMPT,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    intent,
    issue_registry as ir,
    llm,
)

from . import (
    AGENT_ID,
    EventStream,
    completed_event,
    conversation_subentry,
    converse,
    error_event,
    failed_event,
    incomplete_event,
    message_events,
    response_payload,
    tool_args_done,
    tool_call_added,
    tool_events,
    usage_completed_events,
)
from .conftest import ACCESS_TOKEN, ACCOUNT_ID

from tests.common import MockConfigEntry
from tests.components.conversation import (
    MockChatLog,
    mock_chat_log,  # noqa: F401
)

PRIMARY_AGENT_ID = "conversation.grok_primary"
SECONDARY_AGENT_ID = "conversation.grok_secondary"


def _two_agent_entry(template: MockConfigEntry) -> MockConfigEntry:
    """Build an entry with two conversation agents from a fixture template."""
    return MockConfigEntry(
        domain="spacexai",
        title="Home User",
        unique_id=ACCOUNT_ID,
        data=dict(template.data),
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: DEFAULT_MODEL,
                    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                    CONF_MAX_OUTPUT_TOKENS: DEFAULT_MAX_OUTPUT_TOKENS,
                },
                subentry_type="conversation",
                title="Grok Primary",
                unique_id=None,
            ),
            ConfigSubentryData(
                data={
                    CONF_MODEL: "grok-4.3",
                    CONF_LLM_HASS_API: [llm.LLM_API_ASSIST],
                    CONF_MAX_OUTPUT_TOKENS: DEFAULT_MAX_OUTPUT_TOKENS,
                },
                subentry_type="conversation",
                title="Grok Secondary",
                unique_id=None,
            ),
        ],
    )


async def test_conversation_entity_registers_service_device(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Expose a control-capable Conversation entity backed by a service device."""
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert (
        state.attributes["supported_features"]
        == conversation.ConversationEntityFeature.CONTROL
    )

    subentry = conversation_subentry(setup_integration)
    device = device_registry.async_get_device_by_identifier(
        ("spacexai", subentry.subentry_id), setup_integration.entry_id
    )
    assert device is not None
    assert device.manufacturer == "SpaceXAI"
    assert device.model_id == DEFAULT_MODEL
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert (
        conversation.agent_manager.async_get_agent(hass, AGENT_ID).supported_languages
        == "*"
    )


@freeze_time("2026-01-15 12:00:00")
@pytest.mark.usefixtures("setup_integration")
async def test_system_prompt_includes_runtime_identity(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Seed Assist instructions with HA version, model, and provider identity."""
    with patch(
        "homeassistant.components.spacexai.conversation.HA_VERSION",
        "2026.9.0.dev0",
    ):
        await converse(hass, "What versions are you?")
    system_message = next(
        item
        for item in mock_stream.call_args.kwargs["input"]
        if item.get("type") == "message" and item.get("role") == "system"
    )
    assert system_message["content"] == snapshot


@pytest.mark.usefixtures("setup_integration")
async def test_completed_stream_traces_usage_and_closes(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
) -> None:
    """Close the SDK stream and publish token usage on a completed response."""
    trace.async_clear_traces()
    stream = EventStream(
        usage_completed_events(
            "Hello from Grok",
            input_tokens=11,
            cached_tokens=3,
            output_tokens=7,
        )
    )
    mock_stream.return_value = stream

    result = await converse(hass, "Hello")

    assert result.response.response_type is intent.IntentResponseType.ACTION_DONE
    assert result.response.speech["plain"]["speech"] == "Hello from Grok"
    assert stream.closed
    stats = next(
        (
            event["data"]["stats"]
            for trace_obj in trace.async_get_traces()
            for event in trace_obj.as_dict().get("events", [])
            if event.get("event_type") == "agent_detail"
            and event.get("data", {}).get("stats")
        ),
        None,
    )
    assert stats == {
        "input_tokens": 11,
        "cached_input_tokens": 3,
        "output_tokens": 7,
    }


@freeze_time("2026-01-15 12:00:00")
@pytest.mark.usefixtures("setup_integration")
async def test_continuation_reuses_history_and_prompt_cache_key(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Continue a chat with prior turns and the conversation id as cache key."""
    mock_stream.return_value = EventStream(message_events("Hello from Grok"))
    first = await converse(hass, "Hello")

    mock_stream.return_value = EventStream(message_events("Welcome back"))
    second = await converse(hass, "Remember me?", first.conversation_id)

    assert second.conversation_id == first.conversation_id
    assert second.response.speech["plain"]["speech"] == "Welcome back"
    assert mock_stream.call_args.kwargs["prompt_cache_key"] == first.conversation_id
    assert mock_stream.call_args.kwargs["max_output_tokens"] == 2048
    assert mock_stream.call_args.kwargs["input"][1:] == snapshot


@pytest.mark.usefixtures("setup_integration")
async def test_tool_arguments_done_without_name_uses_announced_tool(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Accept xAI streams that omit name on function_call_arguments.done."""
    mock_stream.side_effect = [
        EventStream(
            [
                tool_call_added(
                    item_id="item_0",
                    call_id="call_1",
                    name="test_tool",
                ),
                tool_args_done(
                    item_id="item_0",
                    name=None,
                    arguments='{"value": 1}',
                ),
                completed_event(2),
            ]
        ),
        EventStream(message_events("Done")),
    ]
    mock_chat_log.mock_tool_results({"call_1": {"result": "ok"}})

    result = await converse(hass, "Run tool", mock_chat_log.conversation_id)

    assert result.response.speech["plain"]["speech"] == "Done"
    outputs = [
        item
        for item in mock_stream.call_args.kwargs["input"]
        if item["type"] == "function_call_output"
    ]
    assert [item["call_id"] for item in outputs] == ["call_1"]


@pytest.mark.usefixtures("setup_integration")
async def test_failed_stream_does_not_execute_buffered_tool_calls(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Do not run Assist tools when the provider stream fails after tool args."""
    mock_stream.return_value = EventStream(
        [
            *tool_events(("call_1", "test_tool", '{"value": 1}'), complete=False),
            failed_event("server_error", "failed"),
        ]
    )
    mock_chat_log.mock_tool_results({"call_1": {"result": "should-not-run"}})

    result = await converse(hass, "Run tool", mock_chat_log.conversation_id)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert mock_stream.await_count == 1
    assert not any(
        isinstance(item, conversation.ToolResultContent)
        for item in mock_chat_log.content
    )


@pytest.mark.usefixtures("setup_integration")
async def test_tool_then_text_preserves_provider_output_order(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Keep tool calls ahead of later text when buffering until stream end."""
    mock_stream.return_value = EventStream(
        [
            *tool_events(("call_1", "test_tool", '{"value": 1}'), complete=False),
            *message_events("After the tool", complete=True),
        ]
    )
    mock_chat_log.mock_tool_results({"call_1": {"result": "one"}})

    result = await converse(hass, "Use a tool", mock_chat_log.conversation_id)

    assert result.response.speech["plain"]["speech"] == "After the tool"
    tool_index = next(
        index
        for index, item in enumerate(mock_chat_log.content)
        if isinstance(item, conversation.AssistantContent) and item.tool_calls
    )
    text_index = next(
        index
        for index, item in enumerate(mock_chat_log.content)
        if isinstance(item, conversation.AssistantContent)
        and item.content == "After the tool"
    )
    assert tool_index < text_index


@pytest.mark.usefixtures("setup_integration")
async def test_multiple_tool_calls_in_one_response_are_rejected(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Reject multi-tool responses until ChatLog cancels sibling tool tasks."""
    mock_stream.return_value = EventStream(
        tool_events(
            ("call_1", "test_tool", '{"value": 1}'),
            ("call_2", "test_tool", '{"value": 2}'),
        )
    )
    mock_chat_log.mock_tool_results(
        {
            "call_1": {"result": "one"},
            "call_2": {"result": "two"},
        }
    )

    result = await converse(hass, "Run tools", mock_chat_log.conversation_id)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert mock_stream.await_count == 1
    assert not any(
        isinstance(item, conversation.ToolResultContent)
        for item in mock_chat_log.content
    )


@pytest.mark.usefixtures("setup_integration")
async def test_tool_failure_is_returned_to_provider(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep a Home Assistant tool failure explicit in the model loop."""
    mock_stream.side_effect = [
        EventStream(tool_events(("call_1", "missing_tool", "{}"))),
        EventStream(message_events("The tool failed")),
    ]
    mock_chat_log.mock_tool_results(
        {"call_1": {"error": "HomeAssistantError", "error_text": "Tool not found"}}
    )

    with caplog.at_level(logging.WARNING):
        result = await converse(hass, "Use missing", mock_chat_log.conversation_id)

    assert result.response.speech["plain"]["speech"] == "The tool failed"
    assert "category=home_assistant_tool_failure" in caplog.text
    assert "tool=missing_tool" in caplog.text
    outputs = [
        item
        for item in mock_stream.call_args.kwargs["input"]
        if item["type"] == "function_call_output"
    ]
    assert json.loads(outputs[0]["output"]) == {
        "error": "HomeAssistantError",
        "error_text": "Tool not found",
    }


def test_format_tool_strips_unsupported_top_level_schema_keys() -> None:
    """Strip Assist schema keys that the provider rejects at the top level."""
    tool = MagicMock(spec=llm.Tool)
    tool.name = "test_tool"
    tool.description = "desc"
    tool.parameters = MagicMock()
    with patch(
        "homeassistant.components.spacexai.entity.convert",
        return_value={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "oneOf": [{"required": ["value"]}],
            "enum": ["a"],
        },
    ):
        formatted = _format_tool(tool, None)
    assert formatted["parameters"] == {
        "type": "object",
        "properties": {"value": {"type": "string"}},
    }


@pytest.mark.usefixtures("setup_integration")
async def test_tool_loop_is_bounded(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Stop after MAX_TOOL_ITERATIONS tool rounds without a final answer."""
    mock_stream.side_effect = [
        EventStream(tool_events((f"call_{index}", "test_tool", "{}")))
        for index in range(MAX_TOOL_ITERATIONS)
    ]
    mock_chat_log.mock_tool_results(
        {f"call_{index}": {"result": "ok"} for index in range(MAX_TOOL_ITERATIONS)}
    )

    result = await converse(hass, "Loop", mock_chat_log.conversation_id)

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert mock_stream.await_count == MAX_TOOL_ITERATIONS


@pytest.mark.usefixtures("setup_integration")
async def test_auth_error_starts_reauthentication(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
) -> None:
    """Mark the entity unavailable and start reauth on runtime auth failure."""
    mock_stream.side_effect = ReauthenticationRequiredError(
        "expired",
        context=ErrorContext(operation=Operation.RESPONSE, model=DEFAULT_MODEL),
    )
    result = await converse(hass, "Hello")
    assert result.response.response_type is intent.IntentResponseType.ERROR
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress_by_handler("spacexai")
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


@pytest.mark.usefixtures("setup_integration")
async def test_quota_limited_marks_entity_unavailable(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mark the entity unavailable when the subscription quota is exhausted."""
    mock_stream.side_effect = QuotaLimitedError(
        "quota",
        context=ErrorContext(operation=Operation.RESPONSE, model=DEFAULT_MODEL),
    )
    with caplog.at_level(logging.INFO):
        result = await converse(hass, "Hello")
    assert result.response.response_type is intent.IntentResponseType.ERROR
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "SpaceXAI is unavailable:" in caplog.text
    assert "category=quota_limited" in caplog.text


async def test_subscription_not_entitled_marks_entity_unavailable(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_stream: AsyncMock,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mark the entity unavailable and raise the subscription repair on denial."""
    mock_stream.side_effect = SubscriptionNotEntitledError(
        "subscription",
        context=ErrorContext(operation=Operation.RESPONSE, model=DEFAULT_MODEL),
    )
    with caplog.at_level(logging.INFO):
        result = await converse(hass, "Hello")
    assert result.response.response_type is intent.IntentResponseType.ERROR
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert issue_registry.async_get_issue(
        "spacexai", f"subscription_not_entitled_{setup_integration.entry_id}"
    )
    assert "SpaceXAI is unavailable:" in caplog.text
    assert "category=subscription_not_entitled" in caplog.text


async def test_model_not_entitled_creates_repair_once(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_stream: AsyncMock,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mark the entity unavailable and log the model repair only once."""
    mock_stream.side_effect = ModelNotEntitledError(
        "not entitled",
        context=ErrorContext(operation=Operation.RESPONSE, model=DEFAULT_MODEL),
    )
    issue_id = (
        f"model_not_entitled_{conversation_subentry(setup_integration).subentry_id}"
    )

    with caplog.at_level(logging.INFO):
        await converse(hass, "Hello")
        await converse(hass, "Again")

    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert issue_registry.async_get_issue("spacexai", issue_id)
    assert caplog.text.count("SpaceXAI is unavailable:") == 1


async def test_model_not_entitled_recovers_and_clears_repair(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_stream: AsyncMock,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Clear the model repair after a later successful converse."""
    mock_stream.side_effect = ModelNotEntitledError(
        "not entitled",
        context=ErrorContext(operation=Operation.RESPONSE, model=DEFAULT_MODEL),
    )
    issue_id = (
        f"model_not_entitled_{conversation_subentry(setup_integration).subentry_id}"
    )
    await converse(hass, "Hello")
    assert issue_registry.async_get_issue("spacexai", issue_id)

    mock_stream.side_effect = None
    mock_stream.return_value = EventStream(message_events("Recovered"))
    with caplog.at_level(logging.INFO):
        result = await converse(hass, "Hello again")

    assert result.response.speech["plain"]["speech"] == "Recovered"
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert not issue_registry.async_get_issue("spacexai", issue_id)
    assert "SpaceXAI is available again" in caplog.text


async def test_subscription_not_entitled_recovers_and_clears_repair(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_stream: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Clear the subscription repair after a later successful converse."""
    mock_stream.side_effect = SubscriptionNotEntitledError(
        "subscription",
        context=ErrorContext(operation=Operation.RESPONSE, model=DEFAULT_MODEL),
    )
    subscription_issue = f"subscription_not_entitled_{setup_integration.entry_id}"
    await converse(hass, "Hello")
    assert issue_registry.async_get_issue("spacexai", subscription_issue)

    mock_stream.side_effect = None
    mock_stream.return_value = EventStream(message_events("Recovered"))
    result = await converse(hass, "Hello again")

    assert result.response.speech["plain"]["speech"] == "Recovered"
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert not issue_registry.async_get_issue("spacexai", subscription_issue)


async def test_catalog_restore_marks_entity_available_without_chat(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_validate: AsyncMock,
    issue_registry: ir.IssueRegistry,
    provider_snapshot: ProviderSnapshot,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Restore availability from catalog refresh without requiring a successful chat."""
    mock_validate.return_value = ProviderSnapshot(
        account=AccountInfo(ACCOUNT_ID, "Home User", None),
        models=(ModelInfo("grok-other", "xai"),),
    )
    with caplog.at_level(logging.INFO):
        result = await hass.config_entries.subentries.async_init(
            (setup_integration.entry_id, "conversation"),
            context={"source": "user"},
        )
    assert result["type"] is FlowResultType.FORM
    issue_id = (
        f"model_not_entitled_{conversation_subentry(setup_integration).subentry_id}"
    )
    assert issue_registry.async_get_issue("spacexai", issue_id)
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert "SpaceXAI is unavailable:" in caplog.text
    assert "category=model_not_entitled" in caplog.text

    mock_validate.return_value = provider_snapshot
    with caplog.at_level(logging.INFO):
        result = await hass.config_entries.subentries.async_init(
            (setup_integration.entry_id, "conversation"),
            context={"source": "user"},
        )
    assert result["type"] is FlowResultType.FORM
    assert not issue_registry.async_get_issue("spacexai", issue_id)
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert "SpaceXAI is available again" in caplog.text


async def test_conversation_agent_registers_for_config_entry(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
) -> None:
    """Expose the conversation agent by config entry id while loaded."""
    agent = conversation.agent_manager.async_get_agent(hass, setup_integration.entry_id)
    assert isinstance(agent, conversation.AbstractConversationAgent)

    assert await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()
    assert (
        conversation.agent_manager.async_get_agent(hass, setup_integration.entry_id)
        is None
    )


@pytest.mark.usefixtures("setup_credentials", "mock_validate")
async def test_removing_conversation_keeps_sibling_entry_agent(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Re-register a remaining sibling as the entry-id conversation agent."""
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    entry = _two_agent_entry(mock_config_entry)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    agent = conversation.agent_manager.async_get_agent(hass, entry.entry_id)
    assert isinstance(agent, conversation.AbstractConversationAgent)

    primary = next(
        subentry
        for subentry in entry.subentries.values()
        if subentry.title == "Grok Primary"
    )
    hass.config_entries.async_remove_subentry(entry, primary.subentry_id)
    await hass.async_block_till_done()

    agent = conversation.agent_manager.async_get_agent(hass, entry.entry_id)
    assert isinstance(agent, conversation.AbstractConversationAgent)
    assert hass.states.get(SECONDARY_AGENT_ID) is not None


@pytest.mark.usefixtures("setup_credentials")
async def test_runtime_identity_strips_jinja_from_model_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_validate: AsyncMock,
    mock_stream: AsyncMock,
) -> None:
    """Neutralize Jinja delimiter characters in provider-controlled model IDs."""
    dangerous_model = "grok-{}}{ 7*7 }{%}-x"
    mock_validate.return_value = ProviderSnapshot(
        account=AccountInfo(ACCOUNT_ID, "Home User", None),
        models=(ModelInfo(dangerous_model, "xai"),),
    )
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        conversation_subentry(mock_config_entry),
        data={
            **conversation_subentry(mock_config_entry).data,
            CONF_MODEL: dangerous_model,
        },
    )
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await converse(hass, "Who are you?")
    system_message = next(
        item
        for item in mock_stream.call_args.kwargs["input"]
        if item.get("type") == "message" and item.get("role") == "system"
    )
    content = system_message["content"]
    assert "{" not in content
    assert "}" not in content
    assert "%" not in content
    assert "Conversation model: grok- 7*7 -x" in content


@pytest.mark.usefixtures("setup_integration")
async def test_response_timeout_covers_stream_and_tool_awaits(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
) -> None:
    """Budget one deadline per iteration for stream reads and tool awaits."""
    timeout_enters = 0
    real_timeout_at = asyncio.timeout_at

    @contextlib.asynccontextmanager
    async def counting_timeout_at(when: float) -> Any:
        nonlocal timeout_enters
        timeout_enters += 1
        async with real_timeout_at(when):
            yield

    class ProgressThenStall(EventStream):
        def __init__(self) -> None:
            super().__init__([])
            self._sent = False

        async def __anext__(self) -> ResponseStreamEvent:
            if not self._sent:
                self._sent = True
                return ResponseTextDeltaEvent(
                    content_index=0,
                    delta="Hi",
                    item_id="msg_1",
                    logprobs=[],
                    output_index=0,
                    sequence_number=0,
                    type="response.output_text.delta",
                )
            await asyncio.Event().wait()
            raise StopAsyncIteration

    mock_stream.return_value = ProgressThenStall()
    with (
        patch("homeassistant.components.spacexai.entity.RESPONSE_TIMEOUT", 0.05),
        patch(
            "homeassistant.components.spacexai.entity.asyncio.timeout_at",
            counting_timeout_at,
        ),
    ):
        result = await converse(hass, "Wait")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert (
        result.response.speech["plain"]["speech"]
        == f"SpaceXAI did not finish the response from {DEFAULT_MODEL} in time"
    )
    assert timeout_enters == 1


@pytest.mark.usefixtures("setup_integration")
async def test_cancellation_propagates(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
) -> None:
    """Do not convert task cancellation into a user-facing provider error."""
    mock_stream.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await converse(hass, "Cancel")


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("side_effect", "expected_fragments"),
    [
        pytest.param(
            RuntimeError(f"Authorization: Bearer {ACCESS_TOKEN}; refresh-token"),
            ("_async_handle_chat_log",),
            id="runtime",
        ),
        pytest.param(
            PermanentProviderError(
                f"denied Bearer {ACCESS_TOKEN}",
                context=ErrorContext(operation=Operation.RESPONSE, model=DEFAULT_MODEL),
            ),
            ("category=permanent_provider_failure",),
            id="permanent",
        ),
    ],
)
async def test_error_logging_is_sanitized(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    side_effect: Exception,
    expected_fragments: tuple[str, ...],
) -> None:
    """Keep error logs free of credential material."""
    mock_stream.side_effect = side_effect
    with caplog.at_level(logging.ERROR):
        result = await converse(hass, "Hello")
    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert ACCESS_TOKEN not in caplog.text
    assert "refresh-token" not in caplog.text
    for fragment in expected_fragments:
        assert fragment in caplog.text


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    "events",
    [
        pytest.param([incomplete_event()], id="max-output-tokens"),
        pytest.param([incomplete_event(reason=None)], id="incomplete-unknown"),
        pytest.param([failed_event("server_error", "failed")], id="failed"),
        pytest.param(
            [failed_event("vector_store_timeout", "timeout")],
            id="vector-store-timeout",
        ),
        pytest.param([error_event("stream_error", "failed")], id="error"),
        pytest.param(
            [error_event("rate_limit_exceeded", "limited")],
            id="rate-limit",
        ),
        pytest.param(
            [
                ResponseRefusalDeltaEvent(
                    content_index=0,
                    delta="refused",
                    item_id="message",
                    output_index=0,
                    sequence_number=0,
                    type="response.refusal.delta",
                )
            ],
            id="refusal",
        ),
    ],
)
async def test_lifecycle_stream_errors_are_translated(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    events: list[ResponseStreamEvent],
    snapshot: SnapshotAssertion,
) -> None:
    """Surface provider lifecycle failures as translated Assist errors."""
    mock_stream.return_value = EventStream(events)
    result = await converse(hass, "Hello")
    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech == snapshot


@pytest.mark.usefixtures("setup_integration")
async def test_ignored_progress_events_are_skipped(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
) -> None:
    """Skip protocol progress events and non-reasoning output-item completions."""
    mock_stream.return_value = EventStream(
        [
            ResponseInProgressEvent(
                response=response_payload(status="in_progress"),
                sequence_number=0,
                type="response.in_progress",
            ),
            *message_events("Ready", complete=False),
            ResponseOutputItemDoneEvent(
                item=ResponseOutputMessage(
                    id="msg_1",
                    content=[],
                    role="assistant",
                    status="completed",
                    type="message",
                ),
                output_index=0,
                sequence_number=3,
                type="response.output_item.done",
            ),
            completed_event(4),
        ]
    )
    result = await converse(hass, "Hello")
    assert result.response.speech["plain"]["speech"] == "Ready"


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    "events",
    [
        pytest.param(message_events("Hi", complete=False), id="truncated"),
        pytest.param([completed_event()], id="completed-without-content"),
        pytest.param(
            [
                *message_events("Hi"),
                ResponseTextDeltaEvent(
                    content_index=0,
                    delta="late",
                    item_id="msg_1",
                    logprobs=[],
                    output_index=0,
                    sequence_number=99,
                    type="response.output_text.delta",
                ),
            ],
            id="post-terminal",
        ),
        pytest.param(
            [SimpleNamespace(type="response.totally_unknown")],
            id="unknown-event",
        ),
        pytest.param(
            [
                ResponseOutputItemAddedEvent.model_construct(
                    type="response.output_item.added",
                    output_index=0,
                    sequence_number=0,
                    item=SimpleNamespace(type="web_search_call", id="ws_1"),
                )
            ],
            id="unexpected-output-item",
        ),
    ],
)
async def test_malformed_stream_is_unexpected_response(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    events: list[Any],
) -> None:
    """Surface truncated, empty, late, and unknown streams as unexpected responses."""
    mock_stream.return_value = EventStream(events)
    result = await converse(hass, "Hello")
    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert (
        result.response.speech["plain"]["speech"]
        == f"SpaceXAI returned an unexpected response from {DEFAULT_MODEL}"
    )


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("events", "speech"),
    [
        pytest.param(
            [
                tool_call_added(item_id=None, call_id="call_1", name="test_tool"),
                completed_event(),
            ],
            f"SpaceXAI returned an unexpected response from {DEFAULT_MODEL}",
            id="null-item-id",
        ),
        pytest.param(
            [
                tool_args_done(item_id="fc_1", name="test_tool", arguments="{}"),
                completed_event(),
            ],
            f"SpaceXAI returned an unexpected response from {DEFAULT_MODEL}",
            id="unannounced-args",
        ),
        pytest.param(
            [
                tool_call_added(item_id="fc_1", call_id="", name="test_tool"),
                completed_event(),
            ],
            f"{DEFAULT_MODEL} requested a Home Assistant tool with invalid arguments",
            id="empty-call-id",
        ),
        pytest.param(
            [
                tool_call_added(item_id="fc_1", call_id="call_1", name=""),
                completed_event(),
            ],
            f"{DEFAULT_MODEL} requested a Home Assistant tool with invalid arguments",
            id="empty-name",
        ),
        pytest.param(
            [
                tool_call_added(item_id="fc_1", call_id="call_1", name="test_tool"),
                tool_call_added(item_id="fc_1", call_id="call_2", name="test_tool"),
                completed_event(),
            ],
            f"{DEFAULT_MODEL} requested a Home Assistant tool with invalid arguments",
            id="duplicate-id",
        ),
        pytest.param(
            [
                tool_call_added(item_id="fc_1", call_id="call_1", name="test_tool"),
                tool_args_done(item_id="fc_1", name="other_tool", arguments="{}"),
                completed_event(),
            ],
            f"{DEFAULT_MODEL} requested a Home Assistant tool with invalid arguments",
            id="name-mismatch",
        ),
        pytest.param(
            [
                tool_call_added(item_id="fc_1", call_id="call_1", name="test_tool"),
                tool_args_done(
                    item_id="fc_1",
                    name="test_tool",
                    arguments='{"broken"',
                ),
                completed_event(),
            ],
            f"{DEFAULT_MODEL} requested a Home Assistant tool with invalid arguments",
            id="malformed-json",
        ),
        pytest.param(
            [
                tool_call_added(item_id="fc_1", call_id="call_1", name="test_tool"),
                tool_args_done(item_id="fc_1", name="test_tool", arguments="[]"),
                completed_event(),
            ],
            f"{DEFAULT_MODEL} requested a Home Assistant tool with invalid arguments",
            id="non-object-args",
        ),
        pytest.param(
            [
                tool_call_added(item_id="fc_1", call_id="call_1", name="test_tool"),
                completed_event(),
            ],
            f"{DEFAULT_MODEL} requested a Home Assistant tool with invalid arguments",
            id="unfinished-tool",
        ),
    ],
)
async def test_invalid_tool_stream_is_rejected(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    events: list[Any],
    speech: str,
) -> None:
    """Reject incomplete, duplicate, and malformed tool-call streams."""
    mock_stream.return_value = EventStream(events)
    result = await converse(hass, "Run tool")
    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == speech


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("error", "speech"),
    [
        pytest.param(
            httpx.TimeoutException("read timeout"),
            f"SpaceXAI did not finish the response from {DEFAULT_MODEL} in time",
            id="httpx-timeout",
        ),
        pytest.param(
            httpx.ConnectError("refused"),
            f"Home Assistant could not connect to SpaceXAI while using {DEFAULT_MODEL}",
            id="httpx-connect",
        ),
        pytest.param(
            OpenAIError("schema"),
            f"SpaceXAI rejected the request to {DEFAULT_MODEL}",
            id="sdk-error",
        ),
        pytest.param(
            ValidationError.from_exception_data("Response", []),
            f"SpaceXAI returned an unexpected response from {DEFAULT_MODEL}",
            id="validation",
        ),
    ],
)
async def test_stream_body_errors_are_typed(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    error: Exception,
    speech: str,
) -> None:
    """Map stream-body httpx and SDK failures onto typed Assist errors."""

    class RaisingStream(EventStream):
        async def __anext__(self) -> ResponseStreamEvent:
            raise error

    mock_stream.return_value = RaisingStream(())
    result = await converse(hass, "Hello")
    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert result.response.speech["plain"]["speech"] == speech


@pytest.mark.usefixtures("setup_integration")
async def test_reasoning_summary_opens_and_splits_assistant_turns(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
) -> None:
    """Start a turn for a leading summary and split when summary_index changes."""
    mock_stream.return_value = EventStream(
        [
            ResponseReasoningSummaryTextDeltaEvent(
                delta="First",
                item_id="reasoning-1",
                output_index=0,
                sequence_number=0,
                summary_index=0,
                type="response.reasoning_summary_text.delta",
            ),
            ResponseReasoningSummaryTextDeltaEvent(
                delta="Second",
                item_id="reasoning-1",
                output_index=0,
                sequence_number=1,
                summary_index=1,
                type="response.reasoning_summary_text.delta",
            ),
            *message_events("Done"),
        ]
    )
    result = await converse(hass, "Hello")
    assert result.response.speech["plain"]["speech"] == "Done"
    chat_log = hass.data[conversation.chat_log.DATA_CHAT_LOGS][result.conversation_id]
    thinking = [
        content.thinking_content
        for content in chat_log.content
        if isinstance(content, conversation.AssistantContent)
        and content.thinking_content
    ]
    assert thinking == ["First", "Second"]


@pytest.mark.parametrize(
    ("code", "error_type"),
    [
        pytest.param("insufficient_quota", QuotaLimitedError, id="quota"),
        pytest.param("model_not_found", ModelNotEntitledError, id="model"),
        pytest.param(
            "subscription_required",
            SubscriptionNotEntitledError,
            id="subscription",
        ),
    ],
)
def test_stream_failure_classifies_entitlement_codes(
    code: str, error_type: type[Exception]
) -> None:
    """Map stream failure codes onto the same typed entitlement errors as HTTP."""
    error = _stream_failure(code, model=DEFAULT_MODEL)
    assert isinstance(error, error_type)
    assert error.context.model == DEFAULT_MODEL


async def test_template_error_skips_provider(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    mock_stream: AsyncMock,
) -> None:
    """Return the ChatLog error when prompt rendering fails."""
    subentry = conversation_subentry(setup_integration)
    hass.config_entries.async_update_subentry(
        setup_integration,
        subentry,
        data={**subentry.data, CONF_PROMPT: "{{ invalid("},
    )
    await hass.config_entries.async_reload(setup_integration.entry_id)

    result = await converse(hass, "Hello")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    mock_stream.assert_not_awaited()


@pytest.mark.usefixtures("setup_integration", "mock_stream")
async def test_homeassistant_error_from_chat_loop_is_preserved(
    hass: HomeAssistant,
) -> None:
    """Preserve translated Home Assistant errors from the chat loop."""
    with patch.object(
        SpaceXAIConversationEntity,
        "_async_handle_chat_log",
        side_effect=HomeAssistantError("already translated"),
    ):
        result = await converse(hass, "Hello")
    assert result.response.response_type is intent.IntentResponseType.ERROR


@pytest.mark.usefixtures("setup_integration")
async def test_tool_timeout_is_not_provider_outage(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
) -> None:
    """Do not mark SpaceXAI unavailable when the shared tool-phase deadline expires."""
    mock_stream.return_value = EventStream(message_events("Hello"))
    phase = {"n": 0}
    real_timeout_at = asyncio.timeout_at

    @contextlib.asynccontextmanager
    async def timeout_at_tool_deadline(when: float) -> Any:
        phase["n"] += 1
        if phase["n"] == 1:
            async with real_timeout_at(when):
                yield
            return
        try:
            yield
        finally:
            raise TimeoutError

    with patch(
        "homeassistant.components.spacexai.entity.asyncio.timeout_at",
        timeout_at_tool_deadline,
    ):
        result = await converse(hass, "Hello")

    assert result.response.response_type is intent.IntentResponseType.ERROR
    assert (
        result.response.speech["plain"]["speech"]
        == f"A Home Assistant tool requested by {DEFAULT_MODEL} failed"
    )
    state = hass.states.get(AGENT_ID)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_credentials", "mock_validate")
async def test_auth_and_quota_failures_mark_sibling_agents(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_stream: AsyncMock,
) -> None:
    """Shared account failures mark every agent; model denials stay local."""
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    entry = _two_agent_entry(mock_config_entry)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_stream.side_effect = QuotaLimitedError(
        "quota",
        context=ErrorContext(operation=Operation.RESPONSE, model=DEFAULT_MODEL),
    )
    await converse(hass, "Hello", agent_id=PRIMARY_AGENT_ID)
    assert hass.states.get(PRIMARY_AGENT_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(SECONDARY_AGENT_ID).state == STATE_UNAVAILABLE

    mock_stream.side_effect = None
    mock_stream.return_value = EventStream(message_events("Recovered"))
    result = await converse(hass, "Hello", agent_id=PRIMARY_AGENT_ID)
    assert result.response.speech["plain"]["speech"] == "Recovered"
    assert hass.states.get(PRIMARY_AGENT_ID).state != STATE_UNAVAILABLE
    assert hass.states.get(SECONDARY_AGENT_ID).state != STATE_UNAVAILABLE

    mock_stream.side_effect = ModelNotEntitledError(
        "gone",
        context=ErrorContext(operation=Operation.RESPONSE, model="grok-4.3"),
    )
    await converse(hass, "Hello", agent_id=SECONDARY_AGENT_ID)
    mock_stream.side_effect = None
    mock_stream.return_value = EventStream(message_events("Still ok"))
    await converse(hass, "Hello", agent_id=PRIMARY_AGENT_ID)
    assert hass.states.get(PRIMARY_AGENT_ID).state != STATE_UNAVAILABLE
    assert hass.states.get(SECONDARY_AGENT_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("setup_integration")
async def test_reasoning_summary_is_replayed_on_tool_continuation(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
    mock_chat_log: MockChatLog,  # noqa: F811
) -> None:
    """Rebuild reasoning input from encrypted content plus streamed summary text."""
    reasoning = ResponseReasoningItem(
        id="reasoning-1",
        summary=[],
        encrypted_content="encrypted-plan",
        type="reasoning",
    )
    mock_stream.side_effect = [
        EventStream(
            [
                ResponseOutputItemAddedEvent(
                    item=reasoning,
                    output_index=0,
                    sequence_number=0,
                    type="response.output_item.added",
                ),
                ResponseReasoningSummaryTextDeltaEvent(
                    delta="Plan the tool",
                    item_id="reasoning-1",
                    output_index=0,
                    sequence_number=1,
                    summary_index=0,
                    type="response.reasoning_summary_text.delta",
                ),
                ResponseOutputItemDoneEvent(
                    item=reasoning,
                    output_index=0,
                    sequence_number=2,
                    type="response.output_item.done",
                ),
                *tool_events(("call_1", "test_tool", '{"value": 1}')),
            ]
        ),
        EventStream(message_events("Tool finished")),
    ]
    mock_chat_log.mock_tool_results({"call_1": {"result": "one"}})

    result = await converse(hass, "Use a tool", mock_chat_log.conversation_id)

    assert result.response.speech["plain"]["speech"] == "Tool finished"
    assert mock_stream.await_count == 2
    reasoning_inputs = [
        item
        for item in mock_stream.call_args.kwargs["input"]
        if item.get("type") == "reasoning"
    ]
    assert reasoning_inputs == [
        {
            "type": "reasoning",
            "id": "reasoning-1",
            "summary": [{"type": "summary_text", "text": "Plan the tool"}],
            "encrypted_content": "encrypted-plan",
        }
    ]


@pytest.mark.usefixtures("setup_integration")
async def test_adjacent_stream_deltas_are_coalesced(
    hass: HomeAssistant,
    mock_stream: AsyncMock,
) -> None:
    """Merge adjacent text/thinking deltas while buffering the validated stream."""
    mock_stream.return_value = EventStream(
        [
            ResponseTextDeltaEvent(
                content_index=0,
                delta="He",
                item_id="msg_1",
                logprobs=[],
                output_index=0,
                sequence_number=0,
                type="response.output_text.delta",
            ),
            ResponseTextDeltaEvent(
                content_index=0,
                delta="llo ",
                item_id="msg_1",
                logprobs=[],
                output_index=0,
                sequence_number=1,
                type="response.output_text.delta",
            ),
            ResponseReasoningSummaryTextDeltaEvent(
                delta="Think ",
                item_id="reasoning-1",
                output_index=1,
                sequence_number=2,
                summary_index=0,
                type="response.reasoning_summary_text.delta",
            ),
            ResponseReasoningSummaryTextDeltaEvent(
                delta="twice",
                item_id="reasoning-1",
                output_index=1,
                sequence_number=3,
                summary_index=0,
                type="response.reasoning_summary_text.delta",
            ),
            ResponseTextDeltaEvent(
                content_index=0,
                delta="world",
                item_id="msg_2",
                logprobs=[],
                output_index=2,
                sequence_number=4,
                type="response.output_text.delta",
            ),
            completed_event(5),
        ]
    )
    result = await converse(hass, "Hello")
    assert result.response.speech["plain"]["speech"] == "Hello world"
    chat_log = hass.data[conversation.chat_log.DATA_CHAT_LOGS][result.conversation_id]
    thinking = [
        content.thinking_content
        for content in chat_log.content
        if isinstance(content, conversation.AssistantContent)
        and content.thinking_content
    ]
    assert thinking == ["Think twice"]
