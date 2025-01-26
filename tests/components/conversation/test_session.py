"""Test the conversation session."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.conversation import ConversationInput, session
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
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
    with patch("homeassistant.util.ulid.ulid_now") as mock_ulid_now:
        mock_ulid_now.return_value = "mock-ulid"
        yield mock_ulid_now


@pytest.mark.parametrize(
    ("start_id", "given_id"),
    [
        (None, "mock-ulid"),
        # This ULID is not known as a session
        ("01JHXE0952TSJCFJZ869AW6HMD", "mock-ulid"),
        ("not-a-ulid", "not-a-ulid"),
    ],
)
async def test_conversation_id(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
    mock_ulid: Mock,
    start_id: str | None,
    given_id: str,
) -> None:
    """Test conversation ID generation."""
    mock_conversation_input.conversation_id = start_id
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        assert chat_session.conversation_id == given_id


async def test_cleanup(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Mock cleanup of the conversation session."""
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        assert len(chat_session.messages) == 2
        conversation_id = chat_session.conversation_id

    # Generate session entry.
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        # Because we didn't add a message to the session in the last block,
        # the conversation was not be persisted and we get a new ID
        assert chat_session.conversation_id != conversation_id
        conversation_id = chat_session.conversation_id
        chat_session.async_add_message(
            session.ChatMessage(
                role="assistant",
                agent_id="mock-agent-id",
                content="Hey!",
            )
        )
        assert len(chat_session.messages) == 3

    # Reuse conversation ID to ensure we can chat with same session
    mock_conversation_input.conversation_id = conversation_id
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        assert len(chat_session.messages) == 4
        assert chat_session.conversation_id == conversation_id

    # Set the last updated to be older than the timeout
    hass.data[session.DATA_CHAT_HISTORY][conversation_id].last_updated = (
        dt_util.utcnow() + session.CONVERSATION_TIMEOUT
    )

    async_fire_time_changed(
        hass, dt_util.utcnow() + session.CONVERSATION_TIMEOUT + timedelta(seconds=1)
    )

    # Should not be cleaned up, but it should have scheduled another cleanup
    mock_conversation_input.conversation_id = conversation_id
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        assert len(chat_session.messages) == 4
        assert chat_session.conversation_id == conversation_id

    async_fire_time_changed(
        hass, dt_util.utcnow() + session.CONVERSATION_TIMEOUT * 2 + timedelta(seconds=1)
    )

    # It should be cleaned up now and we start a new conversation
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        assert chat_session.conversation_id != conversation_id
        assert len(chat_session.messages) == 2


def test_chat_message() -> None:
    """Test chat message."""
    with pytest.raises(ValueError):
        session.ChatMessage(role="native", agent_id=None, content="", native=None)


async def test_add_message(
    hass: HomeAssistant, mock_conversation_input: ConversationInput
) -> None:
    """Test filtering of messages."""
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        assert len(chat_session.messages) == 2

        with pytest.raises(ValueError):
            chat_session.async_add_message(
                session.ChatMessage(role="system", agent_id=None, content="")
            )

        # No 2 user messages in a row
        assert chat_session.messages[1].role == "user"

        with pytest.raises(ValueError):
            chat_session.async_add_message(
                session.ChatMessage(role="user", agent_id=None, content="")
            )

        # No 2 assistant messages in a row
        chat_session.async_add_message(
            session.ChatMessage(role="assistant", agent_id=None, content="")
        )
        assert len(chat_session.messages) == 3
        assert chat_session.messages[-1].role == "assistant"

        with pytest.raises(ValueError):
            chat_session.async_add_message(
                session.ChatMessage(role="assistant", agent_id=None, content="")
            )


async def test_message_filtering(
    hass: HomeAssistant, mock_conversation_input: ConversationInput
) -> None:
    """Test filtering of messages."""
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        messages = chat_session.async_get_messages(agent_id=None)
        assert len(messages) == 2
        assert messages[0] == session.ChatMessage(
            role="system",
            agent_id=None,
            content="",
        )
        assert messages[1] == session.ChatMessage(
            role="user",
            agent_id=mock_conversation_input.agent_id,
            content=mock_conversation_input.text,
        )
        # Cannot add a second user message in a row
        with pytest.raises(ValueError):
            chat_session.async_add_message(
                session.ChatMessage(
                    role="user",
                    agent_id="mock-agent-id",
                    content="Hey!",
                )
            )

        chat_session.async_add_message(
            session.ChatMessage(
                role="assistant",
                agent_id="mock-agent-id",
                content="Hey!",
                native="assistant-reply-native",
            )
        )
        # Different agent, will be filtered out.
        chat_session.async_add_message(
            session.ChatMessage(
                role="native", agent_id="another-mock-agent-id", content="", native=1
            )
        )
        chat_session.async_add_message(
            session.ChatMessage(
                role="native", agent_id="mock-agent-id", content="", native=1
            )
        )

    assert len(chat_session.messages) == 5

    messages = chat_session.async_get_messages(agent_id="mock-agent-id")
    assert len(messages) == 4

    assert messages[2] == session.ChatMessage(
        role="assistant",
        agent_id="mock-agent-id",
        content="Hey!",
        native="assistant-reply-native",
    )
    assert messages[3] == session.ChatMessage(
        role="native", agent_id="mock-agent-id", content="", native=1
    )


async def test_llm_api(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
) -> None:
    """Test when we reference an LLM API."""
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        await chat_session.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api="assist",
            user_llm_prompt=None,
        )

    assert isinstance(chat_session.llm_api, llm.APIInstance)
    assert chat_session.llm_api.api.id == "assist"


async def test_unknown_llm_api(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
    snapshot: SnapshotAssertion,
) -> None:
    """Test when we reference an LLM API that does not exists."""
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        with pytest.raises(session.ConverseError) as exc_info:
            await chat_session.async_update_llm_data(
                conversing_domain="test",
                user_input=mock_conversation_input,
                user_llm_hass_api="unknown-api",
                user_llm_prompt=None,
            )

    assert str(exc_info.value) == "Error getting LLM API unknown-api"
    assert exc_info.value.as_conversation_result().as_dict() == snapshot


async def test_template_error(
    hass: HomeAssistant,
    mock_conversation_input: ConversationInput,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that template error handling works."""
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        with pytest.raises(session.ConverseError) as exc_info:
            await chat_session.async_update_llm_data(
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

    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        with patch(
            "homeassistant.auth.AuthManager.async_get_user", return_value=mock_user
        ):
            await chat_session.async_update_llm_data(
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

    assert chat_session.user_name == "Test User"

    assert "The instance name is test home." in chat_session.messages[0].content
    assert "The user name is Test User." in chat_session.messages[0].content
    assert "The user id is 12345." in chat_session.messages[0].content
    assert "The calling platform is test." in chat_session.messages[0].content


async def test_extra_systen_prompt(
    hass: HomeAssistant, mock_conversation_input: ConversationInput
) -> None:
    """Test that extra system prompt works."""
    extra_system_prompt = "Garage door cover.garage_door has been left open for 30 minutes. We asked the user if they want to close it."
    extra_system_prompt2 = (
        "User person.paulus came home. Asked him what he wants to do."
    )
    mock_conversation_input.extra_system_prompt = extra_system_prompt

    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        await chat_session.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=None,
        )
        chat_session.async_add_message(
            session.ChatMessage(
                role="assistant",
                agent_id="mock-agent-id",
                content="Hey!",
            )
        )

    assert chat_session.extra_system_prompt == extra_system_prompt
    assert chat_session.messages[0].content.endswith(extra_system_prompt)

    # Verify that follow-up conversations with no system prompt take previous one
    mock_conversation_input.conversation_id = chat_session.conversation_id
    mock_conversation_input.extra_system_prompt = None

    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        await chat_session.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=None,
        )

    assert chat_session.extra_system_prompt == extra_system_prompt
    assert chat_session.messages[0].content.endswith(extra_system_prompt)

    # Verify that we take new system prompts
    mock_conversation_input.extra_system_prompt = extra_system_prompt2

    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        await chat_session.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=None,
        )
        chat_session.async_add_message(
            session.ChatMessage(
                role="assistant",
                agent_id="mock-agent-id",
                content="Hey!",
            )
        )

    assert chat_session.extra_system_prompt == extra_system_prompt2
    assert chat_session.messages[0].content.endswith(extra_system_prompt2)
    assert extra_system_prompt not in chat_session.messages[0].content

    # Verify that follow-up conversations with no system prompt take previous one
    mock_conversation_input.extra_system_prompt = None

    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        await chat_session.async_update_llm_data(
            conversing_domain="test",
            user_input=mock_conversation_input,
            user_llm_hass_api=None,
            user_llm_prompt=None,
        )

    assert chat_session.extra_system_prompt == extra_system_prompt2
    assert chat_session.messages[0].content.endswith(extra_system_prompt2)
