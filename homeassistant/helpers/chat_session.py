"""Helper to organize chat sessions between integrations."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    HassJob,
    HassJobType,
    HomeAssistant,
    callback,
)
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.ulid import ulid_now, ulid_to_bytes

from .event import async_call_later

DATA_CHAT_SESSION: HassKey[dict[str, ChatSession]] = HassKey("chat_session")
DATA_CHAT_SESSION_CLEANUP: HassKey[SessionCleanup] = HassKey("chat_session_cleanup")

CONVERSATION_TIMEOUT = timedelta(minutes=5)
LOGGER = logging.getLogger(__name__)

current_session: ContextVar[ChatSession | None] = ContextVar(
    "current_session", default=None
)


@dataclass
class ChatSession:
    """Represent a chat session."""

    conversation_id: str
    last_updated: datetime = field(default_factory=dt_util.utcnow)
    _cleanup_callbacks: list[CALLBACK_TYPE] = field(default_factory=list)

    @callback
    def async_updated(self) -> None:
        """Update the last updated time."""
        self.last_updated = dt_util.utcnow()

    @callback
    def async_on_cleanup(self, cb: CALLBACK_TYPE) -> None:
        """Register a callback to clean up the session."""
        self._cleanup_callbacks.append(cb)

    @callback
    def async_cleanup(self) -> None:
        """Call all clean up callbacks."""
        for cb in self._cleanup_callbacks:
            cb()
        self._cleanup_callbacks.clear()


class SessionCleanup:
    """Helper to clean up the stale sessions."""

    unsub: CALLBACK_TYPE | None = None

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the session cleanup."""
        self.hass = hass
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._on_hass_stop)
        self.cleanup_job = HassJob(
            self._cleanup, "chat_session_cleanup", job_type=HassJobType.Callback
        )

    @callback
    def schedule(self) -> None:
        """Schedule the cleanup."""
        if self.unsub:
            return
        self.unsub = async_call_later(
            self.hass,
            CONVERSATION_TIMEOUT.total_seconds() + 1,
            self.cleanup_job,
        )

    @callback
    def _on_hass_stop(self, event: Event) -> None:
        """Cancel the cleanup on shutdown."""
        if self.unsub:
            self.unsub()
        self.unsub = None

    @callback
    def _cleanup(self, now: datetime) -> None:
        """Clean up the history and schedule follow-up if necessary."""
        self.unsub = None
        all_sessions = self.hass.data[DATA_CHAT_SESSION]

        # We mutate original object because current commands could be
        # yielding session based on it.
        for conversation_id, session in list(all_sessions.items()):
            if session.last_updated + CONVERSATION_TIMEOUT < now:
                LOGGER.debug("Cleaning up session %s", conversation_id)
                del all_sessions[conversation_id]
                session.async_cleanup()

        # Still conversations left, check again in timeout time.
        if all_sessions:
            self.schedule()


@contextmanager
def async_get_chat_session(
    hass: HomeAssistant,
    conversation_id: str | None = None,
) -> Generator[ChatSession]:
    """Return a chat session."""
    if session := current_session.get():
        # If a session is already active and it's the requested conversation ID,
        # return that. We won't update the last updated time in this case.
        if session.conversation_id == conversation_id:
            yield session
            return

        # If it's not the same conversation ID, we will create a new session
        # because it might be a conversation agent calling a tool that is talking
        # to another LLM.
        session = None

    all_sessions = hass.data.get(DATA_CHAT_SESSION)
    if all_sessions is None:
        all_sessions = {}
        hass.data[DATA_CHAT_SESSION] = all_sessions
        hass.data[DATA_CHAT_SESSION_CLEANUP] = SessionCleanup(hass)

    if conversation_id is None:
        conversation_id = ulid_now()

    elif conversation_id in all_sessions:
        session = all_sessions[conversation_id]

    else:
        # Conversation IDs are ULIDs. We generate a new one if not provided.
        # If an old ULID is passed in, we will generate a new one to indicate
        # a new conversation was started. If the user picks their own, they
        # want to track a conversation and we respect it.
        try:
            ulid_to_bytes(conversation_id)
            conversation_id = ulid_now()
        except ValueError:
            pass

    if session is None:
        LOGGER.debug("Creating new session %s", conversation_id)
        session = ChatSession(conversation_id)

    current_session.set(session)
    yield session
    current_session.set(None)

    session.last_updated = dt_util.utcnow()
    all_sessions[conversation_id] = session
    hass.data[DATA_CHAT_SESSION_CLEANUP].schedule()
