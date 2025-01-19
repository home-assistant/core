"""Test the conversation session."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.conversation import ConversationInput, session
from homeassistant.core import Context, HomeAssistant
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

    async_fire_time_changed(
        hass, dt_util.utcnow() + session.CONVERSATION_TIMEOUT + timedelta(seconds=1)
    )

    # It should be cleaned up now and we start a new conversation
    async with session.async_get_chat_session(
        hass, mock_conversation_input
    ) as chat_session:
        assert chat_session.conversation_id != conversation_id
        assert len(chat_session.messages) == 2


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
