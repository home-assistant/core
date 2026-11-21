"""Python namespaces and lifetimes for browser and agent console sessions."""

import asyncio
import builtins
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from itertools import count
import secrets
from typing import Any

from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, SESSION_TIMEOUT
from .execution import console_print

# Connections release their session on close, by riding along on the cleanup
# of the connection subscriptions.
CONSOLE_SUBSCRIPTION_KEY = DOMAIN

# Objects kept alive for the frontend to inspect, oldest are let go first.
MAX_TRACKED_OBJECTS = 10000

# How long closing the sessions waits for cancelled code to clean up.
CLOSE_TIMEOUT = 10


@dataclass(slots=True)
class ConsoleSession:
    """State of a console session, kept per user and session ID."""

    session_id: str
    namespace: dict[str, Any]
    # Prefixes object IDs, so an ID from an earlier session, such as one from
    # before a restart, never finds an object of this one.
    instance_id: str = field(default_factory=lambda: secrets.token_hex(4))
    objects: dict[str, Any] = field(default_factory=dict)
    # The ID of each tracked object by its identity, to track it only once.
    # Identities stay valid, as tracking keeps the objects alive.
    object_ids_by_identity: dict[int, str] = field(default_factory=dict)
    object_ids: Iterator[int] = field(default_factory=partial(count, 1))
    connections: set[ActiveConnection] = field(default_factory=set)
    executions: set[asyncio.Task[Any]] = field(default_factory=set)
    cancel_expiry: CALLBACK_TYPE | None = None
    active_requests: int = 0

    def track(self, value: Any) -> str:
        """Keep a reference to an object, so the frontend can inspect it later."""
        if (object_id := self.object_ids_by_identity.get(id(value))) is not None:
            return object_id

        object_id = f"{self.instance_id}-{next(self.object_ids)}"
        self.objects[object_id] = value
        self.object_ids_by_identity[id(value)] = object_id

        if len(self.objects) > MAX_TRACKED_OBJECTS:
            oldest = self.objects.pop(next(iter(self.objects)))
            del self.object_ids_by_identity[id(oldest)]

        return object_id

    def release_objects(self) -> None:
        """Let go of all objects kept alive for inspection."""
        self.objects.clear()
        self.object_ids_by_identity.clear()

    @property
    def subscription_key(self) -> tuple[str, str]:
        """Return the key of the session in the subscriptions of a connection."""
        return (CONSOLE_SUBSCRIPTION_KEY, self.session_id)

    @callback
    def async_close(self) -> None:
        """Stop the session and let go of everything it holds."""
        if self.cancel_expiry is not None:
            self.cancel_expiry()
            self.cancel_expiry = None

        for connection in self.connections:
            connection.subscriptions.pop(self.subscription_key, None)

        self.connections.clear()
        self.release_objects()

        if not self.executions:
            self.namespace.clear()
            return

        # Cancelled code still runs its cleanup, which may need its names.
        stopping = set(self.executions)

        def _release_namespace(execution: asyncio.Task[Any]) -> None:
            stopping.discard(execution)
            if not stopping:
                self.namespace.clear()

        for execution in stopping:
            execution.add_done_callback(_release_namespace)
            execution.cancel()


class SessionNotFoundError(HomeAssistantError):
    """An MCP session does not exist for this user and credential."""


type ConsoleSessions[_Key: tuple[str, ...]] = dict[_Key, ConsoleSession]

# Only there while the console is enabled.
DATA_SESSIONS: HassKey[ConsoleSessions[tuple[str, str]]] = HassKey(DOMAIN)
DATA_MCP_SESSIONS: HassKey[ConsoleSessions[tuple[str, str, str]]] = HassKey(
    f"{DOMAIN}_mcp_sessions"
)
DATA_LLM_SESSIONS: HassKey[ConsoleSessions[tuple[str, str, str, str]]] = HassKey(
    f"{DOMAIN}_llm_sessions"
)


@callback
def async_get_session(
    hass: HomeAssistant, connection: ActiveConnection, session_id: str
) -> ConsoleSession:
    """Return a console session of the user, creating it when needed.

    Only called while the console is enabled.
    """
    sessions = hass.data[DATA_SESSIONS]
    key = (connection.user.id, session_id)
    session = _async_get_session(hass, sessions, key, session_id)

    if connection not in session.connections:
        session.connections.add(connection)
        connection.subscriptions[session.subscription_key] = partial(
            _async_release_session, hass, sessions, key, session, connection
        )

    return session


@asynccontextmanager
async def async_mcp_session(
    hass: HomeAssistant,
    user_id: str,
    credential_id: str,
    session_id: str | None = None,
) -> AsyncIterator[ConsoleSession]:
    """Create an MCP session or resume a handle owned by this credential."""
    sessions = hass.data[DATA_MCP_SESSIONS]
    if session_id is None:
        session_id = secrets.token_urlsafe(24)
        key = (user_id, credential_id, session_id)
    else:
        key = (user_id, credential_id, session_id)
        if key not in sessions:
            raise SessionNotFoundError

    session = _async_get_session(hass, sessions, key, session_id)
    async with _async_use_session(hass, sessions, key, session):
        yield session


@asynccontextmanager
async def async_llm_session(
    hass: HomeAssistant,
    user_id: str,
    platform: str,
    agent_id: str | None,
    conversation_id: str,
) -> AsyncIterator[ConsoleSession]:
    """Keep a local agent's Python namespace isolated to its conversation."""
    sessions = hass.data[DATA_LLM_SESSIONS]
    key = (user_id, platform, agent_id or "", conversation_id)
    session = _async_get_session(hass, sessions, key, conversation_id)
    async with _async_use_session(hass, sessions, key, session):
        yield session


@asynccontextmanager
async def _async_use_session[_Key: tuple[str, ...]](
    hass: HomeAssistant,
    sessions: ConsoleSessions[_Key],
    key: _Key,
    session: ConsoleSession,
) -> AsyncIterator[None]:
    """Keep an agent session alive until its last active request completes."""
    session.active_requests += 1
    try:
        yield
    finally:
        session.active_requests -= 1
        if not session.active_requests and sessions.get(key) is session:
            _async_schedule_expiry(hass, sessions, key, session)


@callback
def async_close_agent_sessions(hass: HomeAssistant, user_id: str) -> None:
    """Close all agent sessions belonging to a user."""
    _async_close_user_sessions(hass.data[DATA_MCP_SESSIONS], user_id)
    _async_close_user_sessions(hass.data[DATA_LLM_SESSIONS], user_id)


@callback
def _async_close_user_sessions[_Key: tuple[str, ...]](
    sessions: ConsoleSessions[_Key], user_id: str
) -> None:
    """Remove a user's sessions before cancelling their running code."""
    for key in list(sessions):
        if key[0] == user_id:
            sessions.pop(key).async_close()


@callback
def _async_get_session[_Key: tuple[str, ...]](
    hass: HomeAssistant,
    sessions: ConsoleSessions[_Key],
    key: _Key,
    session_id: str,
) -> ConsoleSession:
    """Return a session with a live namespace and no pending expiry."""
    if (session := sessions.get(key)) is None:
        session = sessions[key] = ConsoleSession(
            session_id=session_id,
            namespace={
                "__builtins__": builtins,
                "__name__": "__console__",
                "hass": hass,
            },
        )
        session.namespace["print"] = partial(console_print, session)

    if session.cancel_expiry is not None:
        session.cancel_expiry()
        session.cancel_expiry = None

    return session


@callback
def async_stop_executions(
    hass: HomeAssistant, connection: ActiveConnection, session_id: str
) -> None:
    """Stop the code a session of the user is running, if any."""
    if session := hass.data[DATA_SESSIONS].get((connection.user.id, session_id)):
        for execution in session.executions:
            execution.cancel()


async def async_close_sessions[_Key: tuple[str, ...]](
    sessions: ConsoleSessions[_Key],
) -> None:
    """Close all sessions, and give code they still run a moment to clean up."""
    executions = [
        execution for session in sessions.values() for execution in session.executions
    ]

    for session in sessions.values():
        session.async_close()

    sessions.clear()

    if executions:
        await asyncio.wait(executions, timeout=CLOSE_TIMEOUT)


@callback
def _async_release_session(
    hass: HomeAssistant,
    sessions: ConsoleSessions[tuple[str, str]],
    key: tuple[str, str],
    session: ConsoleSession,
    connection: ActiveConnection,
) -> None:
    """Release a session, expiring it a while after its last connection closed.

    Closing a session removes this from its connections, so this only runs for
    sessions that are still in use.
    """
    session.connections.discard(connection)
    if session.connections:
        return

    _async_schedule_expiry(hass, sessions, key, session)


@callback
def _async_schedule_expiry[_Key: tuple[str, ...]](
    hass: HomeAssistant,
    sessions: ConsoleSessions[_Key],
    key: _Key,
    session: ConsoleSession,
) -> None:
    """Expire an idle session after the reconnect timeout."""

    @callback
    def _async_expire(_now: datetime) -> None:
        session.cancel_expiry = None
        del sessions[key]
        session.async_close()

    session.cancel_expiry = async_call_later(hass, SESSION_TIMEOUT, _async_expire)
