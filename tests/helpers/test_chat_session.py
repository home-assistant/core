"""Test the chat session helper."""

import asyncio
from collections.abc import Generator
import contextvars
from datetime import timedelta
from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import chat_session
from homeassistant.util import dt as dt_util, ulid as ulid_util


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
    with chat_session.async_get_chat_session(hass, start_id, context=None) as session:
        assert session.conversation_id == given_id


async def test_context_var(hass: HomeAssistant) -> None:
    """Test context var."""
    with chat_session.async_get_chat_session(hass, context=None) as session:
        with chat_session.async_get_chat_session(
            hass, session.conversation_id, context=None
        ) as session2:
            assert session is session2

        with chat_session.async_get_chat_session(hass, None, context=None) as session2:
            assert session.conversation_id != session2.conversation_id

        with chat_session.async_get_chat_session(
            hass, "something else", context=None
        ) as session2:
            assert session.conversation_id != session2.conversation_id

        with chat_session.async_get_chat_session(
            hass, ulid_util.ulid_now(), context=None
        ) as session2:
            assert session.conversation_id != session2.conversation_id


async def test_cleanup(
    hass: HomeAssistant,
) -> None:
    """Test cleanup of the chat session."""
    with chat_session.async_get_chat_session(hass, context=None) as session:
        conversation_id = session.conversation_id

    # Reuse conversation ID to ensure we can chat with same session
    with chat_session.async_get_chat_session(
        hass, conversation_id, context=None
    ) as session:
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
    with chat_session.async_get_chat_session(
        hass, conversation_id, context=None
    ) as session:
        assert session.conversation_id == conversation_id

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT * 2 + timedelta(seconds=1),
    )

    # It should be cleaned up now and we start a new conversation
    with chat_session.async_get_chat_session(
        hass, conversation_id, context=None
    ) as session:
        assert session.conversation_id != conversation_id


async def test_cleanup_session_in_use(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the cleanup keeps sessions that a turn uses."""
    with chat_session.async_get_chat_session(hass, context=None) as session:
        conversation_id = session.conversation_id

    freezer.tick(chat_session.CONVERSATION_TIMEOUT)
    with (
        chat_session.async_get_chat_session(
            hass, conversation_id, context=None
        ) as session,
        chat_session.async_get_chat_session(hass, "koala", context=None) as new_session,
    ):
        freezer.tick(chat_session.CONVERSATION_TIMEOUT * 2)
        async_fire_time_changed(hass)
        assert hass.data[chat_session.DATA_CHAT_SESSION] == {
            conversation_id: session,
            "koala": new_session,
        }


async def test_cleanup_inherited_session_in_use(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the cleanup keeps a session that an inheriting task still uses."""
    release = asyncio.Event()

    async def use_session(conversation_id: str) -> None:
        with chat_session.async_get_chat_session(hass, conversation_id, context=None):
            await release.wait()

    with chat_session.async_get_chat_session(hass, context=None) as session:
        conversation_id = session.conversation_id
        # The task inherits the current session, like a pipeline run does.
        task = hass.async_create_task(use_session(conversation_id))
        await asyncio.sleep(0)

    freezer.tick(chat_session.CONVERSATION_TIMEOUT * 2)
    async_fire_time_changed(hass)
    assert hass.data[chat_session.DATA_CHAT_SESSION][conversation_id] is session

    release.set()
    await task


async def test_new_session_shared(hass: HomeAssistant) -> None:
    """Test parallel requests share a new session."""

    async def get_session() -> chat_session.ChatSession:
        with chat_session.async_get_chat_session(
            hass, "koala", context=None
        ) as session:
            return session

    with chat_session.async_get_chat_session(hass, "koala", context=None) as session:
        # A new context runs the request like a separate task would.
        assert (
            await asyncio.create_task(get_session(), context=contextvars.Context())
            is session
        )


@pytest.mark.parametrize(
    "owner_user_id",
    [
        pytest.param("owner-user-id", id="user"),
        pytest.param(None, id="no_user"),
    ],
)
async def test_check_owner(hass: HomeAssistant, owner_user_id: str | None) -> None:
    """Test the first user owns the session, also when there is no user."""
    with chat_session.async_get_chat_session(
        hass, context=Context(user_id=owner_user_id)
    ) as session:
        conversation_id = session.conversation_id

    with chat_session.async_get_chat_session(
        hass, conversation_id, context=Context(user_id=owner_user_id)
    ):
        pass

    with (
        pytest.raises(Unauthorized),
        chat_session.async_get_chat_session(
            hass, conversation_id, context=Context(user_id="other-user-id")
        ),
    ):
        pass


async def test_session_owner(hass: HomeAssistant) -> None:
    """Test the user of the first context owns the conversation."""
    owner = Context(user_id="owner-user-id")
    other = Context(user_id="other-user-id")

    with chat_session.async_get_chat_session(hass, context=owner) as session:
        conversation_id = session.conversation_id

        # A nested call checks the owner too.
        with (
            pytest.raises(Unauthorized),
            chat_session.async_get_chat_session(hass, conversation_id, context=other),
        ):
            pass

    with chat_session.async_get_chat_session(hass, conversation_id, context=owner):
        pass

    with chat_session.async_get_chat_session(hass, conversation_id, context=None):
        pass

    with (
        pytest.raises(Unauthorized),
        chat_session.async_get_chat_session(hass, conversation_id, context=other),
    ):
        pass


async def test_session_owner_after_internal_start(hass: HomeAssistant) -> None:
    """Test the first user claims a conversation that started without one."""
    with chat_session.async_get_chat_session(hass, context=None) as session:
        conversation_id = session.conversation_id

    with chat_session.async_get_chat_session(
        hass, conversation_id, context=Context(user_id="owner-user-id")
    ):
        pass

    with (
        pytest.raises(Unauthorized),
        chat_session.async_get_chat_session(
            hass, conversation_id, context=Context(user_id="other-user-id")
        ),
    ):
        pass


@pytest.mark.usefixtures("mock_integration_frame")
async def test_session_without_context(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test leaving out the context is deprecated."""
    with chat_session.async_get_chat_session(hass):
        pass

    assert "calls async_get_chat_session without a context" in caplog.text


async def test_failed_nested_session(hass: HomeAssistant) -> None:
    """Restore the outer context and clean up sessions after a failure."""
    cleanup = Mock()

    def fail_task() -> None:
        with chat_session.async_get_chat_session(hass, context=None) as inner:
            inner.async_on_cleanup(cleanup)
            raise ValueError("Task failed")

    with chat_session.async_get_chat_session(hass, context=None) as outer:
        with pytest.raises(ValueError, match="Task failed"):
            fail_task()
        assert chat_session.current_session.get() is outer
    assert chat_session.current_session.get() is None
    async_fire_time_changed(
        hass,
        dt_util.utcnow() + chat_session.CONVERSATION_TIMEOUT + timedelta(seconds=1),
    )
    await hass.async_block_till_done()
    cleanup.assert_called_once_with()
    assert not hass.data[chat_session.DATA_CHAT_SESSION]
