"""Test the chat session helper."""

from collections.abc import Generator
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import chat_session
from homeassistant.util import dt as dt_util, ulid as ulid_util

from tests.common import async_fire_time_changed


@pytest.fixture
def mock_ulid() -> Generator[Mock]:
    """Mock the ulid library."""
    with patch("homeassistant.helpers.chat_session.ulid_now") as mock_ulid_now:
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
    start_id: str | None,
    given_id: str,
    mock_ulid: Mock,
) -> None:
    """Test conversation ID generation."""
    with chat_session.async_get_chat_session(hass, start_id) as session:
        assert session.conversation_id == given_id


async def test_context_var(hass: HomeAssistant) -> None:
    """Test context var."""
    with chat_session.async_get_chat_session(hass) as session:
        with chat_session.async_get_chat_session(
            hass, session.conversation_id
        ) as session2:
            assert session is session2

        with chat_session.async_get_chat_session(hass, None) as session2:
            assert session.conversation_id != session2.conversation_id

        with chat_session.async_get_chat_session(hass, "something else") as session2:
            assert session.conversation_id != session2.conversation_id

        with chat_session.async_get_chat_session(
            hass, ulid_util.ulid_now()
        ) as session2:
            assert session.conversation_id != session2.conversation_id


async def test_cleanup(
    hass: HomeAssistant,
) -> None:
    """Test cleanup of the chat session."""
    with chat_session.async_get_chat_session(hass) as session:
        conversation_id = session.conversation_id

    # Reuse conversation ID to ensure we can chat with same session
    with chat_session.async_get_chat_session(hass, conversation_id) as session:
        assert session.conversation_id == conversation_id

    # Set the last updated to be older than the timeout
    hass.data[chat_session.DATA_CHAT_SESSION][conversation_id].last_updated = (
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT
    )

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT + timedelta(seconds=1),
    )

    # Should not be cleaned up, but it should have scheduled another cleanup
    with chat_session.async_get_chat_session(hass, conversation_id) as session:
        assert session.conversation_id == conversation_id

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT * 2 + timedelta(seconds=1),
    )

    # It should be cleaned up now and we start a new conversation
    with chat_session.async_get_chat_session(hass, conversation_id) as session:
        assert session.conversation_id != conversation_id
