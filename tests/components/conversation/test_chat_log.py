"""Test the conversation session."""

from collections.abc import Generator
from dataclasses import asdict
from datetime import timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
import voluptuous as vol

from homeassistant.components.conversation import (
    AssistantContent,
    ConversationInput,
    ConverseError,
    ToolResultContent,
    UserContent,
    async_get_chat_log,
)
from homeassistant.components.conversation.chat_log import DATA_CHAT_LOGS
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import chat_session, llm
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed


@pytest.fixture
def mock_conversation_input(hass: HomeAssistant) -> ConversationInput:
    """Return a conversation input instance."""
    return ConversationInput(
        text="Hello",
        context=Context(),
        conversation_id=None,
        agent_id="mock-agent-id",
        device_id=None,
        language="en",
    )


@pytest.fixture
def mock_ulid() -> Generator[Mock]:
    """Mock the ulid library."""
    with patch("homeassistant.helpers.chat_session.ulid_now") as mock_ulid_now:
        mock_ulid_now.return_value = "mock-ulid"
        yield mock_ulid_now


async def test_cleanup(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test cleanup of the chat log."""
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        conversation_id = session.conversation_id
        # Add message so it persists
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(
                agent_id="mock-agent-id",
                content="Hey!",
            )
        )

    assert conversation_id in hass.data[DATA_CHAT_LOGS]

    # Set the last updated to be older than the timeout
    hass.data[chat_session.DATA_CHAT_SESSION][conversation_id].last_updated = (
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT
    )

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT * 2 + timedelta(seconds=1),
    )

    assert conversation_id not in hass.data[DATA_CHAT_LOGS]


async def test_default_content(
    hass: HomeAssistant, mock_conversation_input: ConversationInput
) -> None:
    """Test filtering of messages."""
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log2,
    ):
        assert chat_log is chat_log2
        assert len(chat_log.content) == 2
        assert chat_log.content[0].role == "system"
        assert chat_log.content[0].content == ""
        assert chat_log.content[1].role == "user"
        assert chat_log.content[1].content == mock_conversation_input.text


async def test_llm_api(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test when we reference an LLM API."""
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api="assist",
            user_llm_prompt=None,
        )

    assert isinstance(chat_log.llm_api, llm.APIInstance)
    assert chat_log.llm_api.api.id == "assist"


async def test_unknown_llm_api(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
    snapshot: SnapshotAssertion,
) -> None:
    """Test when we reference an LLM API that does not exists."""
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
        pytest.raises(ConverseError) as exc_info,
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api="unknown-api",
            user_llm_prompt=None,
        )

    assert str(exc_info.value) == "Error getting LLM API unknown-api"
    assert exc_info.value.as_conversation_result().as_dict() == snapshot


async def test_multiple_llm_apis(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test when we reference an LLM API."""

    class MyTool(llm.Tool):
        """Test tool."""

        name = "test_tool"
        description = "Test function"
        parameters = vol.Schema(
            {vol.Optional("param1", description="Test parameters"): str}
        )

    class MyAPI(llm.API):
        """Test API."""

        async def async_get_api_instance(
            self, llm_context: llm.LLMContext
        ) -> llm.APIInstance:
            """Return a list of tools."""
            return llm.APIInstance(self, "My API Prompt", llm_context, [MyTool()])

    api = MyAPI(hass=hass, id="my-api", name="Test")
    llm.async_register_api(hass, api)

    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=["assist", "my-api"],
            user_llm_prompt=None,
        )

    assert chat_log.llm_api
    assert chat_log.llm_api.api.id == "assist|my-api"


async def test_template_error(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that template error handling works."""
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
        pytest.raises(ConverseError) as exc_info,
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt="{{ invalid_syntax",
        )

    assert str(exc_info.value) == "Error rendering prompt"
    assert exc_info.value.as_conversation_result().as_dict() == snapshot


async def test_template_variables(
    hass: HomeAssistant, mock_conversation_input: ConversationInput
) -> None:
    """Test that template variables work."""
    mock_user = Mock()
    mock_user.id = "12345"
    mock_user.name = "Test User"
    mock_conversation_input.context = Context(user_id=mock_user.id)

    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
        patch("homeassistant.auth.AuthManager.async_get_user", return_value=mock_user),
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=(
                "The instance name is {{ ha_name }}. "
                "The user name is {{ user_name }}. "
                "The user id is {{ llm_context.context.user_id }}."
                "The calling platform is {{ llm_context.platform }}."
            ),
        )

    assert "The instance name is test home." in chat_log.content[0].content
    assert "The user name is Test User." in chat_log.content[0].content
    assert "The user id is 12345." in chat_log.content[0].content
    assert "The calling platform is test." in chat_log.content[0].content


async def test_extra_systen_prompt(
    hass: HomeAssistant, mock_conversation_input: ConversationInput
) -> None:
    """Test that extra system prompt works."""
    extra_system_prompt = "Garage door cover.garage_door has been left open for 30 minutes. We asked the user if they want to close it."
    extra_system_prompt2 = (
        "User person.paulus came home. Asked him what he wants to do."
    )
    mock_conversation_input.extra_system_prompt = extra_system_prompt

    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=None,
        )
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(
                agent_id="mock-agent-id",
                content="Hey!",
            )
        )

    assert chat_log.extra_system_prompt == extra_system_prompt
    assert chat_log.content[0].content.endswith(extra_system_prompt)

    # Verify that follow-up conversations with no system prompt take previous one
    conversation_id = chat_log.conversation_id
    mock_conversation_input.extra_system_prompt = None

    with (
        chat_session.async_get_chat_session(hass, conversation_id) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=None,
        )

    assert chat_log.extra_system_prompt == extra_system_prompt
    assert chat_log.content[0].content.endswith(extra_system_prompt)

    # Verify that we take new system prompts
    mock_conversation_input.extra_system_prompt = extra_system_prompt2

    with (
        chat_session.async_get_chat_session(hass, conversation_id) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=None,
        )
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(
                agent_id="mock-agent-id",
                content="Hey!",
            )
        )

    assert chat_log.extra_system_prompt == extra_system_prompt2
    assert chat_log.content[0].content.endswith(extra_system_prompt2)
    assert extra_system_prompt not in chat_log.content[0].content

    # Verify that follow-up conversations with no system prompt take previous one
    mock_conversation_input.extra_system_prompt = None

    with (
        chat_session.async_get_chat_session(hass, conversation_id) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=None,
        )

    assert chat_log.extra_system_prompt == extra_system_prompt2
    assert chat_log.content[0].content.endswith(extra_system_prompt2)


@pytest.mark.parametrize(
    "prerun_tool_tasks",
    [
        (),
        ("mock-tool-call-id",),
        ("mock-tool-call-id", "mock-tool-call-id-2"),
    ],
)
async def test_tool_call(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
    prerun_tool_tasks: tuple[str],
) -> None:
    """Test using the session tool calling API."""

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.return_value = "Test response"

    with patch(
        "homeassistant.helpers.llm.AssistAPI._async_get_tools", return_value=[]
    ) as mock_get_tools:
        mock_get_tools.return_value = [mock_tool]

        with (
            chat_session.async_get_chat_session(hass) as session,
            async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
        ):
            await chat_log.async_update_llm_data(
                conversing_domain="test",
                user_input=mock_conversation_input,
                user_llm_hass_api="assist",
                user_llm_prompt=None,
            )
            content = AssistantContent(
                agent_id=mock_conversation_input.agent_id,
                content="",
                tool_calls=[
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="test_tool",
                        tool_args={"param1": "Test Param"},
                    ),
                    llm.ToolInput(
                        id="mock-tool-call-id-2",
                        tool_name="test_tool",
                        tool_args={"param1": "Test Param"},
                    ),
                ],
            )

            tool_call_tasks = {
                tool_call_id: hass.async_create_task(
                    chat_log.llm_api.async_call_tool(content.tool_calls[0]),
                    tool_call_id,
                )
                for tool_call_id in prerun_tool_tasks
            }

            with pytest.raises(ValueError):
                chat_log.async_add_assistant_content_without_tools(content)

            results = [
                tool_result_content
                async for tool_result_content in chat_log.async_add_assistant_content(
                    content, tool_call_tasks=tool_call_tasks or None
                )
            ]

            assert results[0] == ToolResultContent(
                agent_id=mock_conversation_input.agent_id,
                tool_call_id="mock-tool-call-id",
                tool_result="Test response",
                tool_name="test_tool",
            )
            assert results[1] == ToolResultContent(
                agent_id=mock_conversation_input.agent_id,
                tool_call_id="mock-tool-call-id-2",
                tool_result="Test response",
                tool_name="test_tool",
            )


async def test_tool_call_exception(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test using the session tool calling API."""

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )
    mock_tool.async_call.side_effect = HomeAssistantError("Test error")

    with (
        patch(
            "homeassistant.helpers.llm.AssistAPI._async_get_tools", return_value=[]
        ) as mock_get_tools,
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        mock_get_tools.return_value = [mock_tool]
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api="assist",
            user_llm_prompt=None,
        )
        result = None
        async for tool_result_content in chat_log.async_add_assistant_content(
            AssistantContent(
                agent_id=mock_conversation_input.agent_id,
                content="",
                tool_calls=[
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="test_tool",
                        tool_args={"param1": "Test Param"},
                    )
                ],
            )
        ):
            assert result is None
            result = tool_result_content

    assert result == ToolResultContent(
        agent_id=mock_conversation_input.agent_id,
        tool_call_id="mock-tool-call-id",
        tool_result={"error": "HomeAssistantError", "error_text": "Test error"},
        tool_name="test_tool",
    )


@pytest.mark.parametrize(
    "deltas",
    [
        [],
        # With content
        [
            {"role": "assistant"},
            {"content": "Test"},
        ],
        # With 2 content
        [
            {"role": "assistant"},
            {"content": "Test"},
            {"role": "assistant"},
            {"content": "Test 2"},
        ],
        # With 1 tool call
        [
            {"role": "assistant"},
            {
                "tool_calls": [
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="test_tool",
                        tool_args={"param1": "Test Param 1"},
                    )
                ]
            },
        ],
        # With content and 1 tool call
        [
            {"role": "assistant"},
            {"content": "Test"},
            {
                "tool_calls": [
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="test_tool",
                        tool_args={"param1": "Test Param 1"},
                    )
                ]
            },
        ],
        # With 2 contents and 1 tool call
        [
            {"role": "assistant"},
            {"content": "Test"},
            {
                "tool_calls": [
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="test_tool",
                        tool_args={"param1": "Test Param 1"},
                    )
                ]
            },
            {"role": "assistant"},
            {"content": "Test 2"},
        ],
        # With 2 tool calls
        [
            {"role": "assistant"},
            {
                "tool_calls": [
                    llm.ToolInput(
                        id="mock-tool-call-id",
                        tool_name="test_tool",
                        tool_args={"param1": "Test Param 1"},
                    )
                ]
            },
            {
                "tool_calls": [
                    llm.ToolInput(
                        id="mock-tool-call-id-2",
                        tool_name="test_tool",
                        tool_args={"param1": "Test Param 2"},
                    )
                ]
            },
        ],
    ],
)
async def test_add_delta_content_stream(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
    snapshot: SnapshotAssertion,
    deltas: list[dict],
) -> None:
    """Test streaming deltas."""

    mock_tool = AsyncMock()
    mock_tool.name = "test_tool"
    mock_tool.description = "Test function"
    mock_tool.parameters = vol.Schema(
        {vol.Optional("param1", description="Test parameters"): str}
    )

    async def tool_call(
        hass: HomeAssistant, tool_input: llm.ToolInput, llm_context: llm.LLMContext
    ) -> str:
        """Call the tool."""
        return tool_input.tool_args["param1"]

    mock_tool.async_call.side_effect = tool_call
    expected_delta = []

    async def stream():
        """Yield deltas."""
        for d in deltas:
            yield d
            expected_delta.append(d)

    captured_deltas = []

    with (
        patch(
            "homeassistant.helpers.llm.AssistAPI._async_get_tools", return_value=[]
        ) as mock_get_tools,
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(
            hass,
            session,
            mock_conversation_input,
            chat_log_delta_listener=lambda chat_log, delta: captured_deltas.append(
                delta
            ),
        ) as chat_log,
    ):
        mock_get_tools.return_value = [mock_tool]
        await chat_log.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api="assist",
            user_llm_prompt=None,
        )

        results = []
        async for content in chat_log.async_add_delta_content_stream(
            "mock-agent-id", stream()
        ):
            results.append(content)

            # Interweave the tool results with the source deltas into expected_delta
            if content.role == "tool_result":
                expected_delta.append(asdict(content))

        assert captured_deltas == expected_delta
        assert results == snapshot
        assert chat_log.content[2:] == results


async def test_add_delta_content_stream_errors(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test streaming deltas error handling."""

    async def stream(deltas):
        """Yield deltas."""
        for d in deltas:
            yield d

    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session, mock_conversation_input) as chat_log,
    ):
        # Stream content without LLM API set
        with pytest.raises(ValueError):
            async for _tool_result_content in chat_log.async_add_delta_content_stream(
                "mock-agent-id",
                stream(
                    [
                        {"role": "assistant"},
                        {
                            "tool_calls": [
                                llm.ToolInput(
                                    id="mock-tool-call-id",
                                    tool_name="test_tool",
                                    tool_args={},
                                )
                            ]
                        },
                    ]
                ),
            ):
                pass

        # Non assistant role
        for role in "system", "user":
            with pytest.raises(ValueError):
                async for (
                    _tool_result_content
                ) in chat_log.async_add_delta_content_stream(
                    "mock-agent-id",
                    stream([{"role": role}]),
                ):
                    pass


async def test_chat_log_reuse(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test that we can reuse a chat log."""
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        assert chat_log.conversation_id == session.conversation_id
        assert len(chat_log.content) == 1

        with async_get_chat_log(hass, session) as chat_log2:
            assert chat_log2 is chat_log
            assert len(chat_log.content) == 1

        with async_get_chat_log(hass, session, mock_conversation_input) as chat_log2:
            assert chat_log2 is chat_log
            assert len(chat_log.content) == 2
            assert chat_log.content[1].role == "user"
            assert chat_log.content[1].content == mock_conversation_input.text


async def test_chat_log_continue_conversation(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test continue conversation."""
    with (
        chat_session.async_get_chat_session(hass) as session,
        async_get_chat_log(hass, session) as chat_log,
    ):
        assert chat_log.continue_conversation is False
        chat_log.async_add_user_content(UserContent(mock_conversation_input.text))
        assert chat_log.continue_conversation is False
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(
                agent_id="mock-agent-id",
                content="Hey? ",
            )
        )
        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(
                agent_id="mock-agent-id",
                content="Ποιο είναι το αγαπηµένο σου χρώµα στα ελληνικά;",
            )
        )
        assert chat_log.continue_conversation is True
